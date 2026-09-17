"""Browser click-through checks on the Expo web export (react-native-web).

What this proves: the app flow works end to end in a browser at tablet and phone sizes,
against the front-end mock and against the real FastAPI backend.
What it does NOT prove: native iPad/Android behaviour, or a real DeepSeek call — the model
path here talks to a local stub (fake_deepseek.py).

Usage (from apps/mobile, after `npm install` and creating backend/.venv):
    pip install -r e2e/requirements.txt && python -m playwright install chromium
    python e2e/run_e2e.py                 # builds web exports, starts servers, runs all scenarios (stub model)
    python e2e/run_e2e.py --skip-build
    python e2e/run_e2e.py --real-model    # uses backend/.env (real DeepSeek key); stub-only scenarios are skipped
Screenshots go to e2e/.out/screens/.
"""

from __future__ import annotations

import argparse
import functools
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
MOBILE = HERE.parent
REPO = MOBILE.parent.parent
BACKEND = REPO / "backend"
OUT = HERE / ".out"
SCREENS = OUT / "screens"

MOCK_PORT, HTTP_PORT, API_PORT, STUB_PORT = 8190, 8191, 8110, 8195
API = f"http://127.0.0.1:{API_PORT}"
VIEWPORTS = {"tablet": {"width": 1180, "height": 820}, "phone": {"width": 390, "height": 844}}
MODEL_TIMEOUT_S = 2

sys.path.insert(0, str(HERE))
import fake_deepseek  # noqa: E402


# ---------- infrastructure ----------


def build(out_dir: Path, api_url: str | None) -> None:
    env = {**os.environ, "CI": "1"}
    env.pop("EXPO_PUBLIC_API_BASE_URL", None)
    if api_url:
        env["EXPO_PUBLIC_API_BASE_URL"] = api_url
    cmd = ["npx", "expo", "export", "--platform", "web", "--output-dir", str(out_dir), "--clear"]
    print("build:", out_dir.name, "->", api_url or "mock")
    subprocess.run(cmd, cwd=MOBILE, env=env, check=True, stdout=subprocess.DEVNULL)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def static_server(directory: Path, port: int) -> ThreadingHTTPServer:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_backend(real_model: bool) -> subprocess.Popen:
    python = os.environ.get("BACKEND_PYTHON", str(BACKEND / ".venv" / "bin" / "python"))
    cors = f"http://localhost:{HTTP_PORT},http://127.0.0.1:{HTTP_PORT}"
    cmd = [python, "-m", "uvicorn", "app.main:app", "--port", str(API_PORT)]
    if real_model:
        env_file = BACKEND / ".env"
        if not env_file.exists():
            raise RuntimeError("--real-model needs backend/.env with DEEPSEEK_API_KEY")
        # Key comes from backend/.env via uvicorn; it is never read or printed here.
        cmd += ["--env-file", str(env_file)]
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DEEPSEEK_", "LIVINGMIND_"))}
        env["LIVINGMIND_CORS_ORIGINS"] = cors  # process env wins over --env-file for this one
    else:
        env = {
            **os.environ,
            "LIVINGMIND_CORS_ORIGINS": cors,
            "LIVINGMIND_PLANNER_MODE": "rule",
            "DEEPSEEK_API_KEY": "e2e-stub-key",
            "DEEPSEEK_BASE_URL": f"http://127.0.0.1:{STUB_PORT}",
            "LIVINGMIND_MODEL_TIMEOUT_S": str(MODEL_TIMEOUT_S),
            "LIVINGMIND_DEMO_LOCAL_HOUR": "20",  # peak tariff, so energy advice is deterministic
        }
    proc = subprocess.Popen(
        cmd,
        cwd=BACKEND,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            urllib.request.urlopen(f"{API}/health", timeout=1)
            return proc
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("backend did not start; check backend/.venv")


def reset_backend() -> None:
    urllib.request.urlopen(urllib.request.Request(f"{API}/api/demo/reset?accountId=demo-account", method="POST"), timeout=3)


# ---------- page helpers ----------


def open_app(page: Page, url: str) -> None:
    page.goto(url)
    page.get_by_test_id("composer-input").wait_for(timeout=20000)


def tab(page: Page, name: str) -> None:
    page.get_by_test_id(f"tab-{name}").click()
    page.wait_for_timeout(150)


def set_mode(page: Page, mode: str) -> None:
    page.get_by_test_id(f"mode-{mode}").click()


def send(page: Page, text: str) -> None:
    """Send a chat message and wait for the assistant's plan card (or a system message)."""
    js = (
        "() => ['plan-message', 'system-message', 'assistant-message']"
        ".map(t => document.querySelectorAll(`[data-testid=${t}]`).length).reduce((a, b) => a + b, 0)"
    )
    before = page.evaluate(js)
    page.get_by_test_id("composer-input").fill(text)
    page.get_by_test_id("composer-send").click()
    page.wait_for_function(f"n => ({js})() > n", arg=before, timeout=20000)


def wait_person(page: Page, name: str) -> None:
    page.wait_for_function(
        "name => (document.querySelector('[data-testid=current-person]') || {}).innerText?.includes(name)",
        arg=name,
        timeout=10000,
    )


def switch_person(page: Page, person_id: str, pin: str | None, name: str) -> None:
    tab(page, "me")
    page.get_by_test_id(f"person-option-{person_id}").click()
    if pin is not None:
        page.get_by_test_id("pin-input").fill(pin)
        page.get_by_test_id("pin-submit").click()
    wait_person(page, name)


def body(page: Page) -> str:
    return page.inner_text("body")


def shot(page: Page, name: str) -> None:
    page.wait_for_timeout(450)  # let entrance animations settle
    page.screenshot(path=str(SCREENS / f"{name}.png"), full_page=True)


def last_system(page: Page) -> str:
    return page.get_by_test_id("system-message").last.inner_text()


# ---------- scenarios ----------


def scenario_full_flow(page: Page, url: str, label: str, viewport: str) -> None:
    """PIN switch -> chat -> plan (devices unchanged) -> confirm -> result -> stop."""
    open_app(page, url)
    switch_person(page, "person-chen", "1357", "陈川")
    tab(page, "chat")
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("confirm-plan").wait_for()
    assert "空调设定 22°C" in body(page), "陈川's plan should use 22°C"
    tab(page, "space")
    assert "80%" in body(page), "devices must not change before confirmation"
    tab(page, "chat")
    shot(page, f"{label}-{viewport}-plan")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("result-card").wait_for()
    page.get_by_test_id("service-strip").first.wait_for()
    text = page.get_by_test_id("result-card").inner_text()
    assert "22°C" in text and "10%" in text, text
    shot(page, f"{label}-{viewport}-running")
    page.get_by_test_id("stop-service").first.click()
    page.get_by_text("休息服务已停止", exact=False).wait_for()
    assert page.get_by_test_id("service-strip").count() == 0
    shot(page, f"{label}-{viewport}-stopped")


def scenario_pin_and_evidence(page: Page, url: str) -> None:
    """Wrong PIN is refused; evidence panel is hidden until switched on."""
    open_app(page, url)
    tab(page, "me")
    assert page.get_by_test_id("evidence-panel").count() == 0
    page.get_by_test_id("person-option-person-zhou").click()
    page.get_by_test_id("pin-input").fill("0000")
    page.get_by_test_id("pin-submit").click()
    page.get_by_test_id("pin-error").wait_for()
    assert "PIN 不正确" in page.get_by_test_id("pin-error").inner_text()
    assert "林悦" in page.get_by_test_id("current-person").inner_text()
    page.get_by_test_id("pin-input").fill("8024")
    page.get_by_test_id("pin-submit").click()
    wait_person(page, "周禾")
    page.get_by_test_id("pref-ac-value").filter(has_text="26.5°C").wait_for(timeout=10000)
    assert "25°C" not in page.get_by_text("我的休息偏好", exact=False).locator("..").inner_text()
    page.get_by_test_id("evidence-switch").click()
    page.get_by_test_id("evidence-panel").wait_for()
    shot(page, "me-evidence")


def scenario_guest_and_scenes(page: Page, url: str) -> None:
    open_app(page, url)
    switch_person(page, "person-guest", None, "访客")
    tab(page, "chat")
    assert "访客模式" in body(page)
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("confirm-plan").wait_for()
    assert "访客" in body(page) and "没有读取任何个人偏好" in body(page)
    shot(page, "guest-plan")
    tab(page, "scenes")
    labels = {
        sid: page.get_by_test_id(f"scene-status-{sid}").inner_text().strip()
        for sid in ("scene-rest", "scene-room-temp", "scene-wake")
    }
    assert labels == {"scene-rest": "已实现", "scene-room-temp": "已实现", "scene-wake": "已实现"}, labels
    page.get_by_test_id("scene-card-scene-wake").click()
    page.get_by_text("本次运行还没有这个场景的执行记录", exact=False).wait_for()
    shot(page, "scenes")


def scenario_mock_model(page: Page) -> None:
    """Mock mode never pretends to call a model."""
    open_app(page, f"http://localhost:{MOCK_PORT}/")
    set_mode(page, "model")
    send(page, "我想休息，有点热")
    page.get_by_test_id("confirm-plan").wait_for()
    assert "前端模拟模式没有模型" in body(page)
    shot(page, "mock-model-fallback")


def post_event(page: Page, temp: float) -> dict:
    res = page.request.post(
        f"{API}/api/spaces/space-home-bedroom/events",
        data={
            "context": {"accountId": "demo-account", "personId": "person-lin", "spaceId": "space-home-bedroom"},
            "type": "room_temperature_changed",
            "roomTempC": temp,
        },
    )
    assert res.ok, res.text()
    return res.json()


def scenario_event(page: Page, url: str, label: str, backend_api: bool) -> None:
    """Rest -> simulated room-temperature event -> one automatic adjustment -> cooldown -> stop -> nothing."""
    open_app(page, url)
    set_mode(page, "rule")
    send(page, "我想休息")  # 林悦: AC 25
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("service-strip").first.wait_for()
    page.get_by_test_id("inject-event").first.click()
    page.get_by_text("已自动调整", exact=False).wait_for(timeout=10000)
    msg = last_system(page)
    assert "空调调整到 24°C" in msg and "模拟事件" in msg, msg
    assert "自动调整 1 次" in body(page)
    shot(page, f"{label}-event-adjusted")
    page.get_by_test_id("inject-event").first.click()
    page.get_by_text("未调整：冷却中", exact=False).wait_for(timeout=10000)
    page.get_by_test_id("stop-service").first.click()
    page.get_by_text("休息服务已停止", exact=False).wait_for()
    if backend_api:
        before = page.request.get(f"{API}/api/spaces/space-home-bedroom/devices?accountId=demo-account").json()
        result = post_event(page, 32)
        after = page.request.get(f"{API}/api/spaces/space-home-bedroom/devices?accountId=demo-account").json()
        assert result["outcome"] == "ignored" and after["version"] == before["version"]
    tab(page, "scenes")
    page.get_by_test_id("scene-card-scene-room-temp").click()
    page.get_by_text("自动调整：", exact=False).first.wait_for()
    shot(page, f"{label}-event-timeline")


def scenario_model_paths(page: Page) -> None:
    """Model plan, timeout fallback, and deviation-limit fallback against the backend (stubbed model)."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    set_mode(page, "model")
    send(page, "我想休息，有点热")
    page.get_by_test_id("confirm-plan").wait_for()
    text = body(page)
    assert "模型计划" in text and "deepseek/" in text and "24°C" in text, text[:400]
    shot(page, "http-model-plan")

    send(page, "我想休息，慢一点")
    page.get_by_text("默认方案 / 规则降级：模型响应超过", exact=False).wait_for(timeout=15000)
    shot(page, "http-timeout-fallback")

    send(page, "我想休息，要很亮")
    page.get_by_text("默认方案 / 规则降级：模型建议偏离偏好过大", exact=False).wait_for(timeout=10000)
    shot(page, "http-deviation-fallback")

    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("result-card").wait_for()
    assert "25°C" in page.get_by_test_id("result-card").last.inner_text(), "fallback must use 林悦's own preference"


def last_assistant(page: Page) -> str:
    return page.get_by_test_id("assistant-message").last.inner_text()


def scenario_agents(page: Page, url: str, label: str) -> None:
    """1+2 agents: full-branch trace, direct device command branch, status and out-of-scope answers."""
    open_app(page, url)
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("energy-line").last.wait_for()
    page.get_by_test_id("trace-toggle").last.click()
    panel = page.get_by_test_id("trace-panel").last
    panel.wait_for()
    text = panel.inner_text()
    for name in ["主 Agent", "人物记忆", "Experience Agent", "能源智能", "Space Execution Agent", "Harness"]:
        assert name in text, (name, text)
    if label == "mock":
        assert "前端模拟" in text
    shot(page, f"{label}-agents-trace")

    send(page, "把空调调到24度")
    page.get_by_text("设备指令：空调设定 24°C", exact=False).first.wait_for()
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("result-card").wait_for()
    assert page.get_by_test_id("service-strip").count() == 0, "a device command must not start a rest service"
    assert "24°C" in page.get_by_test_id("result-card").last.inner_text()

    send(page, "空调调到10度")
    assert "没有生成动作" in last_assistant(page)
    send(page, "卧室现在几度")
    assert "24°C" in last_assistant(page)
    send(page, "今天股市怎么样")
    assert "休息" in last_assistant(page)
    shot(page, f"{label}-agents-command")


def scenario_energy_memory(page: Page) -> None:
    """Eco mode applies advice inside the comfort band; editing one's own preference changes the next plan."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    tab(page, "space")
    offline = page.get_by_test_id("offline-energy-simulation")
    offline.wait_for()
    offline_text = offline.inner_text()
    assert "MATD3" in offline_text and "$1.87" in offline_text and "$-0.02" in offline_text, offline_text
    shot(page, "offline-energy-simulation")
    page.get_by_test_id("energy-mode-eco").click()
    page.get_by_text("节能模式：高峰电价时", exact=False).wait_for()
    tab(page, "chat")
    set_mode(page, "rule")
    send(page, "我想休息")
    line = page.get_by_test_id("energy-line").last.inner_text()
    assert "节能模式" in line and "25°C → 25.5°C" in line, line
    assert "空调设定 25.5°C" in body(page)
    shot(page, "energy-eco-plan")

    tab(page, "me")
    assert page.get_by_test_id("pref-ac-value").inner_text().strip() == "25°C"
    page.get_by_test_id("pref-ac-plus").click()
    page.get_by_test_id("pref-ac-plus").click()
    assert page.get_by_test_id("pref-ac-value").inner_text().strip() == "26°C"
    page.get_by_test_id("pref-save").click()
    page.get_by_text("偏好已保存", exact=False).wait_for()
    shot(page, "memory-edited")
    tab(page, "chat")
    send(page, "我想休息")
    assert "空调设定 26.5°C" in page.get_by_test_id("plan-message").last.inner_text()

    switch_person(page, "person-chen", "1357", "陈川")
    assert page.get_by_test_id("pref-ac-value").inner_text().strip() == "22°C", "陈川 sees only his own preference"


def api_get(page: Page, path: str) -> dict:
    res = page.request.get(f"{API}/api{path}")
    assert res.ok, res.status
    return res.json()


def scenario_prepare_demo(page: Page) -> None:
    """One tap before presenting: any messy state goes back to 林悦 · comfort first · initial devices · empty chat."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    tab(page, "scenes")
    page.get_by_test_id("agent-explainer").wait_for()
    assert page.get_by_test_id("explainer-trace").count() == 0
    page.get_by_test_id("explainer-open-chat").click()
    page.get_by_test_id("chat-empty").wait_for()

    # Make a mess: other person, eco mode, a confirmed service, evidence on.
    switch_person(page, "person-chen", "1357", "陈川")
    page.get_by_test_id("evidence-switch").click()
    tab(page, "space")
    page.get_by_test_id("energy-mode-eco").click()
    page.get_by_text("节能模式：高峰电价时", exact=False).wait_for()
    tab(page, "chat")
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("service-strip").wait_for()
    assert page.get_by_test_id("chat-empty").count() == 0
    tab(page, "scenes")
    page.get_by_test_id("explainer-trace").wait_for()
    page.get_by_test_id("trace-toggle").click()
    assert "Experience Agent" in page.get_by_test_id("trace-panel").inner_text()
    shot(page, "scenes-explainer")
    assert api_get(page, "/spaces/space-home-bedroom/devices?accountId=demo-account")["lightBrightness"] != 80

    tab(page, "me")
    page.get_by_test_id("prepare-demo").click()
    wait_person(page, "林悦")
    page.get_by_test_id("chat-empty").wait_for()
    page.get_by_text("演示已准备好", exact=False).wait_for()
    assert page.get_by_test_id("plan-message").count() == 0
    assert page.get_by_test_id("service-strip").count() == 0
    devices = api_get(page, "/spaces/space-home-bedroom/devices?accountId=demo-account")
    assert (devices["lightBrightness"], devices["acTargetTempC"], devices["curtainOpenPercent"]) == (80, 26, 100), devices
    space = api_get(page, "/bootstrap?accountId=demo-account")["spaces"][0]
    assert space["energyMode"] == "comfort_first", space
    assert "80%" in body(page)
    shot(page, "prepare-demo")
    # Info notices fade on their own after 3 s.
    page.wait_for_timeout(3600)
    assert page.get_by_text("演示已准备好", exact=False).count() == 0
    tab(page, "space")
    assert "舒适优先：只给出节能建议" in body(page)
    assert page.get_by_test_id("evidence-panel-space").count() == 0, "evidence is hidden again"


def scenario_night(page: Page, url: str, label: str, backend_api: bool) -> None:
    """Step 7: schedule preview -> confirm -> fast-forward -> auto-play to wake-up -> completed."""
    open_app(page, url)
    set_mode(page, "rule")
    send(page, "我想休息")  # 林悦
    page.get_by_test_id("schedule-toggle").click()
    preview = page.get_by_test_id("plan-schedule").inner_text()
    for at in ["23:00", "01:00", "06:30", "06:45", "07:00"]:
        assert at in preview, preview
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("night-strip").first.wait_for()
    assert "模拟时间 22:30" in page.get_by_test_id("night-clock").first.inner_text()
    page.get_by_test_id("clock-next").first.click()
    page.get_by_text("模拟时间 23:00 · 入睡：关灯", exact=False).wait_for(timeout=10000)
    assert "整晚安排 1/5" in page.get_by_test_id("night-strip").first.inner_text()
    shot(page, f"{label}-night-first-step")
    page.get_by_test_id("clock-auto").first.click()
    page.get_by_text("唤醒完成，整晚服务已结束", exact=False).wait_for(timeout=30000)
    assert page.get_by_test_id("service-strip").count() == 0, "a completed service has no running strip"
    text = body(page)
    for line in ["模拟时间 01:00 · 深夜：空调调高到 26°C", "模拟时间 06:30 · 唤醒 1/3", "模拟时间 07:00 · 唤醒 3/3"]:
        assert line in text, line
    if backend_api:
        d = page.request.get(f"{API}/api/spaces/space-home-bedroom/devices?accountId=demo-account").json()
        assert (d["lightBrightness"], d["acTargetTempC"], d["curtainOpenPercent"]) == (60, 25, 100), d
    shot(page, f"{label}-night-completed")
    tab(page, "space")
    assert "已完成" in body(page)
    steps = page.get_by_test_id("night-schedule").inner_text()
    assert steps.count("已执行") == 5, steps
    assert "模拟时间 07:00" in steps
    shot(page, f"{label}-night-space")
    tab(page, "scenes")
    page.get_by_test_id("scene-card-scene-wake").click()
    page.get_by_text("唤醒完成", exact=False).first.wait_for()
    shot(page, f"{label}-night-timeline")


def scenario_night_stop(page: Page, url: str) -> None:
    """Stopping mid-night cancels every remaining step."""
    open_app(page, url)
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("clock-next").first.click()
    page.get_by_text("模拟时间 23:00", exact=False).first.wait_for(timeout=10000)
    page.get_by_test_id("stop-service").first.click()
    page.get_by_text("未执行的整晚步骤已取消", exact=False).wait_for()
    tab(page, "space")
    steps = page.get_by_test_id("night-schedule").inner_text()
    assert steps.count("已执行") == 1 and steps.count("已取消") == 4, steps
    assert page.get_by_test_id("clock-next").count() == 0


def scenario_real_model(page: Page) -> None:
    """Real provider: a model plan (or a clearly labelled fallback) appears, then confirm and stop."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    set_mode(page, "model")
    started = time.monotonic()
    send(page, "我想休息，有点热")
    elapsed = int((time.monotonic() - started) * 1000)
    page.get_by_test_id("confirm-plan").wait_for(timeout=30000)
    text = body(page)
    assert ("模型计划" in text) or ("默认方案 / 规则降级" in text), "plan source must be labelled"
    print(f"  real-model: submit -> plan shown in {elapsed} ms ({'model' if '请求模型 · deepseek/' in text else 'fallback'})")
    shot(page, "real-model-plan")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("result-card").wait_for()
    page.get_by_test_id("stop-service").first.click()
    page.get_by_text("休息服务已停止", exact=False).wait_for()
    shot(page, "real-model-stopped")


def scenario_offline(page: Page, backend: subprocess.Popen) -> None:
    """Backend goes away: the app reports it and never fakes success."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    set_mode(page, "rule")
    send(page, "我想休息")
    page.get_by_test_id("confirm-plan").wait_for()
    backend.terminate()
    backend.wait(timeout=10)
    page.get_by_test_id("confirm-plan").click()
    page.get_by_text("无法连接后端", exact=False).first.wait_for(timeout=15000)
    assert "可能已过期" in body(page)
    assert page.get_by_test_id("result-card").count() == 0
    assert page.get_by_test_id("service-strip").count() == 0
    shot(page, "http-offline")


# ---------- main ----------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--real-model", action="store_true", help="use backend/.env (real DeepSeek) instead of the stub")
    args = parser.parse_args()

    SCREENS.mkdir(parents=True, exist_ok=True)
    for old in SCREENS.glob("*.png"):  # screenshots always belong to this run only
        old.unlink()
    mock_dir, http_dir = OUT / "web-mock", OUT / "web-http"
    if not args.skip_build:
        build(mock_dir, None)
        build(http_dir, API)

    servers = [static_server(mock_dir, MOCK_PORT), static_server(http_dir, HTTP_PORT)]
    stub = fake_deepseek.serve(STUB_PORT)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    backend = start_backend(args.real_model)

    results: list[tuple[str, str]] = []
    errors: list[str] = []

    def run(name: str, fn) -> None:
        page = browser.new_page(viewport=VIEWPORTS["tablet"])
        page.on("pageerror", lambda e: errors.append(f"{name}: {e}"))
        try:
            fn(page)
            results.append((name, "ok"))
        except Exception as exc:  # report and continue
            results.append((name, f"FAILED: {exc}"))
            shot(page, f"FAILED-{name}")
        finally:
            page.close()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for vp in VIEWPORTS:
                def mock_flow(page, vp=vp):
                    page.set_viewport_size(VIEWPORTS[vp])
                    scenario_full_flow(page, f"http://localhost:{MOCK_PORT}/", "mock", vp)

                def http_flow(page, vp=vp):
                    reset_backend()
                    page.set_viewport_size(VIEWPORTS[vp])
                    scenario_full_flow(page, f"http://localhost:{HTTP_PORT}/", "http", vp)

                run(f"mock-flow-{vp}", mock_flow)
                run(f"http-flow-{vp}", http_flow)
            run("mock-model-fallback", scenario_mock_model)
            run("mock-event", lambda page: scenario_event(page, f"http://localhost:{MOCK_PORT}/", "mock", False))

            def http_event(page):
                reset_backend()
                scenario_event(page, f"http://localhost:{HTTP_PORT}/", "http", True)

            run("http-event", http_event)

            def http_pin(page):
                reset_backend()
                scenario_pin_and_evidence(page, f"http://localhost:{HTTP_PORT}/")

            run("http-pin-evidence", http_pin)
            run("mock-pin-evidence", lambda page: scenario_pin_and_evidence(page, f"http://localhost:{MOCK_PORT}/"))

            def http_guest(page):
                reset_backend()
                scenario_guest_and_scenes(page, f"http://localhost:{HTTP_PORT}/")

            run("http-guest-scenes", http_guest)

            run("mock-agents", lambda page: scenario_agents(page, f"http://localhost:{MOCK_PORT}/", "mock"))

            def http_agents(page):
                reset_backend()
                scenario_agents(page, f"http://localhost:{HTTP_PORT}/", "http")

            run("http-agents", http_agents)

            def http_energy_memory(page):
                reset_backend()
                scenario_energy_memory(page)

            run("http-energy-memory", http_energy_memory)

            def http_night(page):
                reset_backend()
                scenario_night(page, f"http://localhost:{HTTP_PORT}/", "http", True)

            run("http-night", http_night)
            run("mock-night", lambda page: scenario_night(page, f"http://localhost:{MOCK_PORT}/", "mock", False))

            def phone_night_stop(page):
                reset_backend()
                page.set_viewport_size(VIEWPORTS["phone"])
                scenario_night_stop(page, f"http://localhost:{HTTP_PORT}/")

            run("http-night-stop-phone", phone_night_stop)

            def http_prepare_demo(page):
                reset_backend()
                scenario_prepare_demo(page)

            run("http-prepare-demo", http_prepare_demo)

            if args.real_model:
                def real_model(page):
                    reset_backend()
                    scenario_real_model(page)

                run("http-real-model", real_model)
            else:
                def model_paths(page):
                    reset_backend()
                    scenario_model_paths(page)

                run("http-model-paths", model_paths)

            def offline(page):
                reset_backend()
                scenario_offline(page, backend)

            run("http-offline", offline)  # must be last: stops the backend
            browser.close()
    finally:
        if backend.poll() is None:
            backend.terminate()
        stub.shutdown()
        for s in servers:
            s.shutdown()

    print()
    for name, status in results:
        print(f"  {status:<8} {name}" if status == "ok" else f"  {name}: {status}")
    if errors:
        print("page errors:", *errors, sep="\n  ")
    failed = [r for r in results if r[1] != "ok"] or errors
    print(f"\n{len(results) - len([r for r in results if r[1] != 'ok'])}/{len(results)} scenarios passed; screenshots in {SCREENS}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
