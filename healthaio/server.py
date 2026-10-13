"""A small web server: the page files plus one JSON endpoint per page.

Binds to 127.0.0.1 by default. The data is only read; it changes by editing or importing the CSV files. The one
thing the browser can write is a goal (POST /api/goals: set one, or answer an assistant's proposal), added as a line
to goals.jsonl next to healthaio.toml, and only from a page this server served itself.
"""
import json
import mimetypes
import re
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit

from . import goal_log, kit
from .config import Config
from .context import Context
from .modules import PAGES

WEB = Path(__file__).resolve().parent / "web"
PARAM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")


def payload(cfg: Config, name: str, param: Optional[str] = None, now: Optional[datetime] = None) -> Any:
    if name == "settings":
        return cfg.public()
    if name == "kit":  # the design kit's manifest, for the gallery page (#kit)
        return kit.manifest()
    ctx = Context(goal_log.apply(cfg), now=now)  # the goals set on the Goals page, laid over healthaio.toml
    return PAGES[name](ctx, param)


def to_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def make_handler(cfg: Config, now: Callable[[], Optional[datetime]] = lambda: None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "healthaio"

        def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
            if cfg.demo is False and "--verbose" in sys.argv:
                super().log_message(fmt, *args)

        def _send(self, status: int, body: bytes, kind: str, cache: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_HEAD(self) -> None:
            self.do_GET()

        def _same_site(self) -> bool:
            # only this app's own page may write: a page on any other site (or a DNS name pointed at this computer)
            # sends another Origin or Host, and JSON forces the browser to ask first, which this server never answers
            host = self.headers.get("Host", "")
            name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
            return (name in ("127.0.0.1", "localhost", "[::1]", self.server.server_address[0])
                    and self.headers.get("Origin") == f"http://{host}"
                    and self.headers.get("Content-Type", "").split(";")[0].strip() == "application/json")

        def do_POST(self) -> None:
            if urlsplit(self.path).path != "/api/goals":
                return self._send(404, to_json({"error": "nothing to write here"}), "application/json")
            if not self._same_site():
                return self._send(403, to_json({"error": "goals can only be changed from this app's own page"}), "application/json")
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= 8192:
                return self._send(413, to_json({"error": "expected a small JSON body"}), "application/json")
            try:
                entry = goal_log.from_browser(cfg, json.loads(self.rfile.read(length)), now())
            except ValueError as error:  # GoalError, ConfigError and bad JSON are all ValueErrors
                return self._send(400, to_json({"error": str(error)}), "application/json")
            return self._send(200, to_json({"ok": True, "id": entry["id"]}), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            path = url.path
            if path.startswith("/api/"):
                name = path[len("/api/"):]
                if name not in ("settings", "kit") and name not in PAGES:
                    return self._send(404, to_json({"error": "unknown page"}), "application/json")
                query = parse_qs(url.query)
                param = (query.get("day") or query.get("week") or [None])[0]
                if param is not None and not PARAM.match(param):
                    return self._send(400, to_json({"error": "expected YYYY-MM-DD"}), "application/json")
                try:
                    body = to_json(payload(cfg, name, param, now()))
                except Exception as error:  # show the page an error, keep the server up
                    print(f"[healthaio] {name} failed: {error!r}", file=sys.stderr)
                    return self._send(500, to_json({"error": "this page could not be computed; see the server log"}),
                                      "application/json")
                return self._send(200, body, "application/json; charset=utf-8")
            target = (WEB / ("index.html" if path in ("", "/") else path.lstrip("/"))).resolve()
            if WEB not in target.parents or not target.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if kind.startswith("text/") or kind.endswith(("javascript", "json", "svg+xml")):
                kind += "; charset=utf-8"
            self._send(200, target.read_bytes(), kind, cache="no-cache")

    return Handler


class Server(ThreadingHTTPServer):
    # the page loads about a dozen scripts at once; the stdlib backlog of 5 resets some of those connections,
    # and a module that fails to load leaves the page on "Loading…"
    request_queue_size = 128
    daemon_threads = True


def serve(cfg: Config, host: str = "127.0.0.1", port: int = 8790,
          now: Callable[[], Optional[datetime]] = lambda: None) -> None:
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"[healthaio] warning: listening on {host}; anyone who can reach this address can read your data.",
              file=sys.stderr)
    httpd = Server((host, port), make_handler(cfg, now))
    print(f"Health AIO on http://{'localhost' if host in ('127.0.0.1', '::1') else host}:{port}  (data: {cfg.data_dir})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
