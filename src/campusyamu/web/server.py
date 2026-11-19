"""Serves the CampusYamu web page. It has no data endpoints.

    uv run python -m campusyamu.web              # http://127.0.0.1:8770
    uv run python -m campusyamu.web --port 8771

GET /           serves the built React app (frontend/dist/) when present, falling back
        to the legacy static page (src/campusyamu/web/static/index.html).
GET /config.js  the page's public settings from .env: SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY
                (sign-in), CAMPUSYAMU_API_BASE_URL (optional). Only these public values, never secrets.

The page gets all its data from the CampusYamu API (campusyamu.api, `make api`,
port 8780), the same /v1 endpoints the mobile app uses, so run both.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from campusyamu.core import settings

LEGACY_STATIC = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = Path(os.getenv("CAMPUSYAMU_HOME", str(REPO_ROOT))) / "frontend" / "dist"
DEFAULT_PORT = settings.get("web.port", 8770)
API_PORT = settings.get("api.port", 8780)


def page_config() -> dict[str, str | None]:
    """Public settings for the page. The publishable key is meant for browsers; secrets never go here."""

    return {"supabaseUrl": os.getenv("SUPABASE_URL") or None,
            "supabaseKey": os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or None,
            "apiBaseUrl": os.getenv("CAMPUSYAMU_API_BASE_URL") or None}

MIME_OVERRIDES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _active_web_root() -> Path:
    if (FRONTEND_DIST / "index.html").is_file():
        return FRONTEND_DIST
    return LEGACY_STATIC


def _guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


class PageHandler(BaseHTTPRequestHandler):
    server_version = "CampusYamuWeb/0.3"

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        root = _active_web_root().resolve()
        raw_path = unquote(urlparse(self.path).path)
        rel_path = raw_path.lstrip("/")

        if not rel_path or rel_path == "index.html":
            index_file = root / "index.html"
            self._send(200, index_file.read_bytes(), "text/html; charset=utf-8", "no-store")
            return

        candidate = (root / rel_path).resolve()
        if not candidate.is_relative_to(root):
            self._send(403, b"Forbidden", "text/plain; charset=utf-8")
            return

        if candidate.is_file():
            cache_control = (
                "public, max-age=31536000, immutable"
                if rel_path.startswith("assets/")
                else "no-store"
            )
            self._send(200, candidate.read_bytes(), _guess_content_type(candidate), cache_control)
            return

        # SPA fallback for client routes without a file extension
        if "." not in Path(rel_path).name:
            index_file = root / "index.html"
            if index_file.is_file():
                self._send(200, index_file.read_bytes(), "text/html; charset=utf-8", "no-store")
                return

        self._send(
            404,
            b"Not found. Data lives in the CampusYamu API (/v1, port 8780).",
            "text/plain; charset=utf-8",
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[web] {self.address_string()} {fmt % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default=settings.get("web.host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    from campusyamu.knowledge_graph.handbook_prose import _load_env

    try:
        _load_env(None)                                 # .env: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY
    except Exception as exc:
        print(f"warning: could not load .env: {exc}", file=sys.stderr)
    try:
        server = ThreadingHTTPServer((args.host, args.port), PageHandler)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f"Port {args.port} is in use; try --port {args.port + 1}", file=sys.stderr)
            return 1
        raise
    active = _active_web_root()
    print(
        f"CampusYamu web page on http://{args.host}:{args.port} (serving {active})  "
        f"[API: `make api` -> http://127.0.0.1:{API_PORT}/docs]"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
