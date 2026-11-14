"""Serves the CampusYamu web page. It has no data endpoints.

    uv run python -m campusyamu.web              # http://127.0.0.1:8770
    uv run python -m campusyamu.web --port 8771

GET /   the form + results page (src/campusyamu/web/static/index.html)

The page gets all its data from the CampusYamu API (campusyamu.api, `make api`,
port 8780), the same /v1 endpoints the mobile app uses, so run both. The API
address is API_BASE_URL at the top of the page's script.
"""

from __future__ import annotations

import argparse
import errno
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from campusyamu.core import settings

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = settings.get("web.port", 8770)
API_PORT = settings.get("api.port", 8780)


class PageHandler(BaseHTTPRequestHandler):
    server_version = "CampusYamuWeb/0.2"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path in ("/", "/index.html"):
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"Not found. Data lives in the CampusYamu API (/v1, port 8780).",
                       "text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[web] {self.address_string()} {fmt % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default=settings.get("web.host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    try:
        server = ThreadingHTTPServer((args.host, args.port), PageHandler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f"Port {args.port} is in use; try --port {args.port + 1}", file=sys.stderr)
            return 1
        raise
    print(f"CampusYamu web page on http://{args.host}:{args.port}  "
          f"(it needs the API: `make api` -> http://127.0.0.1:{API_PORT}/docs)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
