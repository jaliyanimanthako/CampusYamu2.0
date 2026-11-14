"""Run the API:  uv run python -m campusyamu.api [--host 0.0.0.0] [--port 8780] [--env-file .env]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from campusyamu.core import settings

DEFAULT_PORT = settings.get("api.port", 8780)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CampusYamu API server (FastAPI + Uvicorn).")
    parser.add_argument("--host", default=settings.get("api.host", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    try:
        _load_env(args.env_file)      # before create_app: CORS origins and keys come from the environment
    except Exception as exc:
        print(f"warning: could not load env file: {exc}", file=sys.stderr)

    import uvicorn

    from .app import create_app
    from .auth import SupabaseAuth

    auth = SupabaseAuth()
    print(f"CampusYamu API docs on http://{args.host}:{args.port}/docs")
    print(f"Sign-in: Supabase ({auth.url})" if auth.enabled else
          "Sign-in: OFF (no SUPABASE_URL) - the API is open and the chat has no memory; local development only")
    uvicorn.run(create_app(auth=auth), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
