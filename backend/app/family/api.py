"""Mount the simulator as its own small API, with its own OpenAPI document."""
from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .profile import create_family_session
from .service import FamilyError
from .speaker_upload import MAX_AUDIO, check_upload, identify_upload, speaker_status


def family_app():
    api = FastAPI(title="LivingMind · Family evening simulator", version="1.0")
    session = create_family_session()

    @api.exception_handler(FamilyError)
    async def family_error(_, exc):
        return JSONResponse(status_code=exc.status, content=exc.payload)

    @api.get("/state")
    def get_family_state():
        return session.dispatch("GET", "/state")

    api.add_api_route("/speaker/status", speaker_status, methods=["GET"])

    @api.post("/speaker/identify")
    async def identify_speaker(request: Request):
        size = request.headers.get("content-length")
        if size is not None and not size.isdecimal():
            raise FamilyError(400, "INVALID_LENGTH", "无效录音文件长度")
        check_upload(int(size) if size is not None else None, request.headers.get("content-type", ""))
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_AUDIO:
                raise FamilyError(413, "AUDIO_SIZE", "请选择 12 MiB 以内的 WAV 文件。")
            data.extend(chunk)
        return await run_in_threadpool(identify_upload, data)

    def mutation(path):
        def apply(payload: dict = Body(...)):
            return session.dispatch("POST", path, payload)
        return apply

    for path in ("/events", "/decision", "/devices", "/reset", "/next-day"):
        api.add_api_route(path, mutation(path), methods=["POST"], name="family_" + path[1:].replace("-", "_"))
    return api
