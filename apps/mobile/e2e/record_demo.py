"""Record the three demo clips on the Expo web export (for D / demo packaging).

Clips (tablet size, backend + virtual devices, rule mode):
  01-user-trigger   "我想休息" -> plan card (trace, overnight schedule) -> confirm -> devices change
  02-event-adjust   running service -> simulated room temperature -> one automatic adjustment
  03-night-stop     fast-forward + auto-play to 07:00 (service completes), then a new night stopped by hand

Every frame carries a caption saying it is the web build with virtual devices and a simulated
clock/event. This is NOT a recording of a native tablet build.

Usage (from apps/mobile):  python e2e/record_demo.py [--skip-build]
Output: e2e/.out/videos/*.mp4 (git-ignored).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_e2e as e2e  # noqa: E402

VIDEOS = e2e.OUT / "videos"
SIZE = e2e.VIEWPORTS["tablet"]
BASE_NOTE = "网页版录屏 · 后端虚拟设备 · 规则模式"

CAPTION_JS = """
(() => {
  const mount = () => {
    if (document.getElementById('demo-caption')) return;
    const d = document.createElement('div');
    d.id = 'demo-caption';
    d.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:99999;' +
      'background:rgba(15,23,42,.82);color:#fff;padding:6px 14px;border-radius:999px;' +
      'font:600 13px -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif;pointer-events:none;white-space:nowrap';
    document.body.appendChild(d);
  };
  window.__setCaption = (t) => { mount(); document.getElementById('demo-caption').textContent = t; };
})();
"""


def caption(page: Page, text: str) -> None:
    page.evaluate("t => window.__setCaption(t)", f"{text} ｜ {BASE_NOTE}")


def pause(page: Page, ms: int = 1200) -> None:
    page.wait_for_timeout(ms)


def type_and_send(page: Page, text: str) -> None:
    box = page.get_by_test_id("composer-input")
    box.click()
    box.press_sequentially(text, delay=120)
    pause(page, 500)
    before = page.get_by_test_id("plan-message").count() + page.get_by_test_id("assistant-message").count()
    page.get_by_test_id("composer-send").click()
    page.wait_for_function(
        "n => document.querySelectorAll('[data-testid=plan-message],[data-testid=assistant-message]').length > n",
        arg=before,
        timeout=20000,
    )


def scroll_chat(page: Page, px: int) -> None:
    page.mouse.move(400, 400)
    page.mouse.wheel(0, px)
    pause(page, 900)


def clip_user_trigger(page: Page) -> None:
    caption(page, "① 用户触发：一句话 → 计划 → 确认")
    pause(page, 1800)
    type_and_send(page, "我想休息")
    caption(page, "① 计划卡：设备尚未改变；来源、能源建议、整晚安排都写明")
    pause(page, 2500)
    page.get_by_test_id("trace-toggle").last.click()
    caption(page, "① 1+2 Agent 协作过程：主 Agent 编排，只有 Experience Agent 可调用模型")
    pause(page, 1000)
    scroll_chat(page, 350)
    pause(page, 2500)
    page.get_by_test_id("schedule-toggle").click()
    caption(page, "① 整晚安排随计划一起确认（模拟时钟）")
    scroll_chat(page, 350)
    pause(page, 2000)
    caption(page, "① 确认后才执行：执行器写入虚拟设备并回读")
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("result-card").wait_for()
    scroll_chat(page, 800)
    pause(page, 3500)


def start_service(page: Page) -> None:
    type_and_send(page, "我想休息")
    pause(page, 800)
    page.get_by_test_id("confirm-plan").click()
    page.get_by_test_id("service-strip").first.wait_for()
    scroll_chat(page, 1500)


def clip_event(page: Page) -> None:
    caption(page, "② 事件调整：先开始一次休息服务")
    pause(page, 1200)
    start_service(page)
    pause(page, 1500)
    caption(page, "② 模拟室温升高 3°C（没有真实传感器）")
    pause(page, 1500)
    page.get_by_test_id("inject-event").first.click()
    page.get_by_text("已自动调整", exact=False).wait_for(timeout=10000)
    caption(page, "② 服务自动调整一次空调：冷却 30 秒、最多 3 次、不超出偏好 ±3°C")
    scroll_chat(page, 800)
    pause(page, 3500)
    page.get_by_test_id("inject-event").first.click()
    page.get_by_text("未调整：冷却中", exact=False).wait_for(timeout=10000)
    caption(page, "② 冷却中再次触发：忽略并说明原因")
    scroll_chat(page, 800)
    pause(page, 3000)
    e2e.tab(page, "scenes")
    page.get_by_test_id("scene-card-scene-room-temp").click()
    caption(page, "② 场景页：执行记录来自后端活动数据")
    pause(page, 3500)


def clip_night(page: Page) -> None:
    caption(page, "③ 整晚服务：同一个服务贯穿整晚")
    pause(page, 1200)
    start_service(page)
    caption(page, "③ 模拟时间 22:30；点“快进”到下一步")
    pause(page, 2500)
    page.get_by_test_id("clock-next").first.click()
    page.get_by_text("模拟时间 23:00 · 入睡：关灯", exact=False).wait_for(timeout=10000)
    scroll_chat(page, 800)
    pause(page, 2500)
    caption(page, "③ 自动播放：每步只执行一次，07:00 唤醒完成后服务结束")
    page.get_by_test_id("clock-auto").first.click()
    page.get_by_text("唤醒完成，整晚服务已结束", exact=False).wait_for(timeout=30000)
    scroll_chat(page, 1500)
    pause(page, 3000)
    e2e.tab(page, "space")
    caption(page, "③ 空间页：整晚时间线 5 步已执行，设备保持唤醒后的状态")
    pause(page, 4000)
    e2e.tab(page, "chat")
    caption(page, "③ 手动停止：新的一晚，执行一步后停止")
    pause(page, 1000)
    start_service(page)
    page.get_by_test_id("clock-next").first.click()
    page.get_by_text("模拟时间 23:00", exact=False).last.wait_for(timeout=10000)
    pause(page, 1500)
    page.get_by_test_id("stop-service").first.click()
    page.get_by_text("未执行的整晚步骤已取消", exact=False).wait_for()
    scroll_chat(page, 1500)
    pause(page, 2500)
    e2e.tab(page, "space")
    caption(page, "③ 停止后：剩余 4 步已取消，设备保持当前状态")
    pause(page, 4000)


CLIPS = [("01-user-trigger", clip_user_trigger), ("02-event-adjust", clip_event), ("03-night-stop", clip_night)]


def to_mp4(src: Path, dst: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        shutil.copy(src, dst.with_suffix(".webm"))
        print("ffmpeg not found; kept", dst.with_suffix(".webm").name)
        return
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(dst)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    http_dir = e2e.OUT / "web-http"
    if not args.skip_build:
        e2e.build(http_dir, e2e.API)
    VIDEOS.mkdir(parents=True, exist_ok=True)
    raw = VIDEOS / "raw"
    shutil.rmtree(raw, ignore_errors=True)
    server = e2e.static_server(http_dir, e2e.HTTP_PORT)
    backend = e2e.start_backend(real_model=False)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for name, fn in CLIPS:
                e2e.reset_backend()
                ctx = browser.new_context(viewport=SIZE, record_video_dir=str(raw / name), record_video_size=SIZE)
                ctx.add_init_script(CAPTION_JS)
                page = ctx.new_page()
                e2e.open_app(page, f"http://localhost:{e2e.HTTP_PORT}/")
                fn(page)
                video = page.video
                ctx.close()
                to_mp4(Path(video.path()), VIDEOS / f"{name}.mp4")
                print("recorded", name)
            browser.close()
    finally:
        backend.terminate()
        server.shutdown()
    shutil.rmtree(raw, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
