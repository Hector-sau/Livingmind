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
    page.get_by_role("button", name="生成休息计划").wait_for(timeout=20000)


def generate(page: Page, utterance: str | None = None, mode: str | None = None) -> None:
    if mode:
        page.get_by_test_id(f"mode-{mode}").click()
    if utterance is not None:
        page.get_by_label("需求输入").fill(utterance)
    page.get_by_role("button", name="生成休息计划").click()
    page.get_by_text("休息计划").first.wait_for()


def body(page: Page) -> str:
    return page.inner_text("body")


def shot(page: Page, name: str) -> None:
    page.screenshot(path=str(SCREENS / f"{name}.png"), full_page=True)


# ---------- scenarios ----------


def scenario_full_flow(page: Page, url: str, label: str, viewport: str) -> None:
    """Pick person -> plan (devices unchanged) -> confirm -> running -> stop."""
    open_app(page, url)
    page.get_by_text("陈川", exact=True).click()
    generate(page, "我想休息", "rule")
    page.get_by_test_id("confirm-plan").wait_for()
    text = body(page)
    assert "空调设定 22°C" in text, "陈川's plan should use 22°C"
    assert "80%" in text, "devices must not change before confirmation"
    shot(page, f"{label}-{viewport}-plan")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_text("运行中", exact=True).wait_for()
    page.wait_for_timeout(500)
    text = body(page)
    assert "22°C" in text and "10%" in text
    shot(page, f"{label}-{viewport}-running")
    page.get_by_test_id("stop-service").click()
    page.get_by_text("已停止", exact=True).wait_for()
    shot(page, f"{label}-{viewport}-stopped")


def scenario_mock_model(page: Page) -> None:
    """Mock mode never pretends to call a model."""
    open_app(page, f"http://localhost:{MOCK_PORT}/")
    generate(page, "我想休息，有点热", "model")
    page.get_by_test_id("confirm-plan").wait_for()
    text = body(page)
    assert "前端模拟模式没有模型" in text
    shot(page, "mock-model-fallback")


def scenario_model_paths(page: Page) -> None:
    """Model plan, timeout fallback, and deviation-limit fallback against the backend (stubbed model)."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    generate(page, "我想休息，有点热", "model")
    page.get_by_test_id("confirm-plan").wait_for()
    text = body(page)
    assert "模型计划" in text and "deepseek/" in text and "24°C" in text, text[:400]
    shot(page, "http-model-plan")

    generate(page, "慢一点")
    page.get_by_text("默认方案 / 规则降级", exact=False).wait_for(timeout=15000)
    assert "模型响应超过" in body(page)
    shot(page, "http-timeout-fallback")

    generate(page, "我想休息，要很亮")
    page.get_by_text("默认方案 / 规则降级：模型建议偏离偏好过大", exact=False).wait_for(timeout=10000)
    shot(page, "http-deviation-fallback")

    page.get_by_test_id("confirm-plan").click()
    page.get_by_text("运行中", exact=True).wait_for()
    page.wait_for_timeout(500)
    assert "25°C" in body(page), "fallback must use 林悦's own preference"


def scenario_real_model(page: Page) -> None:
    """Real provider: a model plan (or a clearly labelled fallback) appears, then confirm and stop."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    started = time.monotonic()
    generate(page, "我想休息，有点热", "model")
    page.get_by_test_id("confirm-plan").wait_for(timeout=30000)
    elapsed = int((time.monotonic() - started) * 1000)
    text = body(page)
    assert ("模型计划" in text) or ("默认方案 / 规则降级" in text), "plan source must be labelled"
    print(f"  real-model: submit -> plan shown in {elapsed} ms ({'model' if '请求模型 · deepseek/' in text else 'fallback'})")
    shot(page, "real-model-plan")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_text("运行中", exact=True).wait_for()
    page.get_by_test_id("stop-service").click()
    page.get_by_text("已停止", exact=True).wait_for()
    shot(page, "real-model-stopped")


def scenario_offline(page: Page, backend: subprocess.Popen) -> None:
    """Backend goes away: the app reports it and never fakes success."""
    open_app(page, f"http://localhost:{HTTP_PORT}/")
    generate(page, "我想休息", "rule")
    page.get_by_test_id("confirm-plan").wait_for()
    backend.terminate()
    backend.wait(timeout=10)
    page.get_by_test_id("confirm-plan").click()
    page.get_by_text("无法连接后端", exact=False).wait_for(timeout=15000)
    text = body(page)
    assert "可能已过期" in text and "80%" in text and "运行中" not in text
    shot(page, "http-offline")


# ---------- main ----------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--real-model", action="store_true", help="use backend/.env (real DeepSeek) instead of the stub")
    args = parser.parse_args()

    SCREENS.mkdir(parents=True, exist_ok=True)
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
