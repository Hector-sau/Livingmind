"""Opt-in local WAV comparison. Reads enrolled templates and never changes family state."""
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path

from .service import FamilyError, MEMBERS
from .speaker_model import MODEL_FILES

MAX_AUDIO = 12 * 1024 * 1024
_worker = threading.BoundedSemaphore(1)


def config():
    model = os.environ.get("FAMILY_VOICE_MODEL")
    directory = os.environ.get("FAMILY_VOICE_PROFILES")
    if not model or not directory:
        return None
    model = Path(model).resolve()
    directory = Path(directory).resolve()
    templates = [directory / (member[0] + ".json") for member in MEMBERS]
    templates = [path for path in templates if path.is_file()]
    if len(templates) < 2 or not all((model / name).is_file() for name in MODEL_FILES):
        return None
    return model, templates


def speaker_status():
    return {"configured": config() is not None, "maxBytes": MAX_AUDIO}


def check_upload(size, content_type):
    if config() is None:
        raise FamilyError(503, "SPEAKER_DISABLED", "请先在本机配置模型与至少两位成员的注册模板。")
    if content_type.partition(";")[0].strip().lower() not in {"audio/wav", "audio/x-wav", "audio/wave"}:
        raise FamilyError(415, "EXPECTED_WAV", "请选择 PCM WAV 录音。")
    if size is not None and not 0 < size <= MAX_AUDIO:
        raise FamilyError(413, "AUDIO_SIZE", "请选择 12 MiB 以内的非空 WAV 文件。")


def identify_upload(data):
    settings = config()
    if settings is None:
        raise FamilyError(503, "SPEAKER_DISABLED", "声音比对尚未配置。")
    model, templates = settings
    if not 0 < len(data) <= MAX_AUDIO:
        raise FamilyError(413, "AUDIO_SIZE", "请选择 12 MiB 以内的非空 WAV 文件。")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            if not (8000 <= rate <= 48000 and rate <= frames <= 30 * rate and
                    wav.getnchannels() in (1, 2) and wav.getsampwidth() in (1, 2, 3, 4)):
                raise ValueError
            if len(wav.readframes(frames)) != frames * wav.getnchannels() * wav.getsampwidth():
                raise ValueError
    except (ValueError, EOFError, wave.Error):
        raise FamilyError(422, "INVALID_AUDIO", "请使用 1–30 秒、8–48 kHz 的单声道或双声道 PCM WAV。")
    if not _worker.acquire(blocking=False):
        raise FamilyError(429, "SPEAKER_BUSY", "正在处理另一段录音，请稍后重试。")
    try:
        with tempfile.TemporaryDirectory(prefix="family-speaker-") as private_dir:
            clip = Path(private_dir) / "recording.wav"
            clip.write_bytes(data)
            runtime = os.environ.get("FAMILY_VOICE_PYTHON") or sys.executable
            command = [runtime, str(Path(__file__).with_name("speaker_model.py")), "--model", str(model),
                       "identify", str(clip), *(str(path) for path in templates)]
            try:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise FamilyError(503, "SPEAKER_UNAVAILABLE", "声纹运行环境未就绪或处理超时，请手动选择说话人。")
            if proc.returncode:
                if "silent or invalid" in proc.stderr:
                    raise FamilyError(422, "NO_SPEECH", "录音中未检测到可用的声音，请重试。")
                raise FamilyError(503, "SPEAKER_UNAVAILABLE", "请检查本机声纹依赖和注册模板。")
            result = json.loads(proc.stdout)
            return {"candidate": result["candidate"], "comparison": result["comparison"],
                    "scores": result["scores"], "threshold": result["threshold"],
                    "requiredMargin": result["required_margin"], "deviceAuthorized": False}
    finally:
        _worker.release()
