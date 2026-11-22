"""Run the local family simulation API and App using only Python's standard library."""
import argparse
import json
import re
import sqlite3
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.family.profile import create_family_session
from app.family.service import FamilyError
from app.family.speaker_upload import check_upload, identify_upload, speaker_status

DEFAULT_STATIC = Path(__file__).resolve().parents[1] / "apps" / "family-demo"


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".vtt": "text/vtt", ".md": "text/plain; charset=utf-8"}

    def json_response(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def family_request(self):
        path = urlsplit(self.path).path.removeprefix("/api/family")
        try:
            if self.command == "GET" and path == "/speaker/status":
                return self.json_response(200, speaker_status())
            if self.command == "POST" and path == "/speaker/identify":
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise FamilyError(400, "INVALID_LENGTH", "无效录音文件长度")
                check_upload(size, self.headers.get("Content-Type", ""))
                return self.json_response(200, identify_upload(self.rfile.read(size)))
            data = {}
            if self.command == "POST":
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8192:
                    raise FamilyError(400, "BAD_BODY", "请求需为 1–8192 字节 JSON")
                data = json.loads(self.rfile.read(size))
            self.json_response(200, self.server.session.dispatch(self.command, path, data))
        except FamilyError as exc:
            self.json_response(exc.status, exc.payload)
        except (ValueError, UnicodeError):
            self.json_response(400, {"error": {"code": "INVALID_JSON", "message": "无效 JSON"}})

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/showcase":
            self.send_response(301)
            self.send_header("Location", "/showcase/")
            self.end_headers()
            return
        if route == "/showcase/media/family-evening.mp4":
            return self.serve_film()
        if route.startswith("/api/family/"):
            self.family_request()
        else:
            super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path == "/showcase/media/family-evening.mp4":
            return self.serve_film()
        super().do_HEAD()

    def serve_film(self):
        # Safari and other media players use byte ranges to start and seek local video.
        film = Path(self.translate_path(self.path))
        if not film.is_file():
            return self.send_error(404)
        size = film.stat().st_size
        start, end = 0, size - 1
        byte_range = self.headers.get("Range")
        if byte_range:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range)
            if match and any(match.groups()):
                first, last = match.groups()
                if first:
                    start = int(first)
                    end = min(int(last), size - 1) if last else size - 1
                else:
                    start = max(0, size - int(last))
            else:
                start = size
            if not 0 <= start <= end < size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        self.send_response(206 if byte_range else 200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        remaining = end - start + 1
        with film.open("rb") as stream:
            stream.seek(start)
            while remaining:
                chunk = stream.read(min(remaining, 65536))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    def do_POST(self):
        self.family_request()

    def translate_path(self, path):
        # The shareable film page serves only its document and the accompanying media.
        route = urlsplit(path).path
        docs = DEFAULT_STATIC.parents[1] / "docs"
        if route == "/showcase/":
            return str(docs / "index.html")
        if route == "/showcase/family-film.md":
            return str(docs / "family-film.md")
        if route.startswith("/showcase/media/"):
            name = route[len("/showcase/media/"):]
            if name and Path(name).name == name and Path(name).suffix in {".jpg", ".gif", ".mp4", ".vtt"}:
                return str(docs / "media" / name)
        return super().translate_path(path)

    def list_directory(self, path):
        self.send_error(404)
        return None


def make_server(port, static=DEFAULT_STATIC, miot_profile=None, state_db=None):
    session = create_family_session(miot_profile, state_db)
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(static)))
    server.session = session
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static", type=Path, default=DEFAULT_STATIC)
    parser.add_argument("--miot-profile", type=Path, help="JSON file of property address bindings for the virtual gateway")
    parser.add_argument("--state-db", type=Path, help="SQLite file for a restartable, locally shared household")
    args = parser.parse_args()
    if not args.static.is_dir():
        parser.error(f"Static App directory missing: {args.static}")
    try:
        server = make_server(args.port, args.static, args.miot_profile, args.state_db)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    with server:
        print(f"LivingMind family simulation: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
