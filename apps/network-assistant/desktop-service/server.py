from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from codex_tasks import CodexTaskCollector
from diagnostics import collect_diagnostics


APP_VERSION = "0.2.0"
STATIC_ROOT = Path(__file__).resolve().parent / "static"
API_PREFIXES = ("/api/", "/netcheck/api/")
STATIC_PREFIX = "/netcheck/"


class DiagnosticServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        peer: str,
        ping_attempts: int,
        codex_home: Path | None,
    ):
        super().__init__(server_address, handler)
        self.peer = peer
        self.ping_attempts = ping_attempts
        self.run_lock = threading.Lock()
        self.codex_tasks = CodexTaskCollector(codex_home)


class Handler(BaseHTTPRequestHandler):
    server: DiagnosticServer

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"{self.address_string()} - {format_string % args}")

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _api_path(self) -> str | None:
        path = urlsplit(self.path).path
        for prefix in API_PREFIXES:
            if path.startswith(prefix):
                return "/api/" + path[len(prefix) :]
        return None

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        api_path = self._api_path()
        if api_path == "/api/health":
            self._send_json({"ok": True, "version": APP_VERSION, "peer": self.server.peer})
            return
        if api_path == "/api/echo":
            self._send_json({"ok": True})
            return
        if api_path == "/api/codex/tasks":
            if self.headers.get("X-Codex-Widget") != "1":
                self._send_json({"ok": False, "error": "missing_widget_header"}, HTTPStatus.FORBIDDEN)
                return
            try:
                self._send_json(self.server.codex_tasks.collect())
            except Exception as exc:
                print(f"Codex task collection failed: {exc!r}")
                self._send_json({"ok": False, "error": "codex_state_unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if api_path:
            self._send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._serve_static()

    def do_POST(self) -> None:
        api_path = self._api_path()
        if api_path != "/api/run":
            self._send_json({"ok": False, "error": "not_found"}, HTTPStatus.NOT_FOUND)
            return

        if self.headers.get("X-Network-Diagnostic") != "1":
            self._send_json({"ok": False, "error": "missing_diagnostic_header"}, HTTPStatus.FORBIDDEN)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._send_json({"ok": False, "error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0 or content_length > 1024:
            self._send_json({"ok": False, "error": "request_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        if content_length:
            self.rfile.read(content_length)

        if not self.server.run_lock.acquire(blocking=False):
            self._send_json({"ok": False, "error": "diagnostic_already_running"}, HTTPStatus.CONFLICT)
            return
        try:
            result = collect_diagnostics(self.server.peer, self.server.ping_attempts)
            self._send_json(result)
        except Exception as exc:  # Keep internal command details out of the mobile response.
            print(f"diagnostic failed: {exc!r}")
            self._send_json({"ok": False, "error": "diagnostic_failed"}, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            self.server.run_lock.release()

    def _serve_static(self) -> None:
        request_path = unquote(urlsplit(self.path).path)
        if request_path == STATIC_PREFIX.rstrip("/"):
            self.send_response(HTTPStatus.PERMANENT_REDIRECT)
            self.send_header("Location", request_path + "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if request_path.startswith(STATIC_PREFIX):
            request_path = "/" + request_path[len(STATIC_PREFIX) :]
        if request_path in ("", "/"):
            request_path = "/index.html"

        relative = request_path.lstrip("/")
        candidate = (STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(STATIC_ROOT.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            if "." not in Path(relative).name:
                candidate = STATIC_ROOT / "index.html"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if candidate.suffix in {".html", ".js", ".css", ".webmanifest"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self' http://127.0.0.1:* http://localhost:* http://[::1]:* "
            "https://www.gstatic.com https://connectivitycheck.gstatic.com https://www.baidu.com; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        if candidate.name in {"sw.js", "index.html", "manifest.webmanifest"}:
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        if candidate.name == "sw.js":
            self.send_header("Service-Worker-Allowed", "./")
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tailnet-only mobile network diagnostics dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="listen address; keep 127.0.0.1 when using Tailscale Serve")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--peer", default="V2359A", help="fixed Tailscale peer hostname, DNS name, node ID, or 100.x address")
    parser.add_argument("--ping-attempts", type=int, default=6, choices=range(3, 11), metavar="3-10")
    parser.add_argument("--codex-home", type=Path, help="read-only Codex state root; defaults to CODEX_HOME or ~/.codex")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = DiagnosticServer(
        (args.host, args.port),
        Handler,
        peer=args.peer,
        ping_attempts=args.ping_attempts,
        codex_home=args.codex_home,
    )
    print(f"Network diagnostics listening on http://{args.host}:{args.port}/ for peer {args.peer}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
