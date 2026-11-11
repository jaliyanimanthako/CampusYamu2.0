"""Minimal `.env` loading for the standalone command-line adapter."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_environment(env_file: Path | None = None) -> Path | None:
    """Load the first available env file without replacing existing variables."""

    candidates = (env_file,) if env_file else (Path.cwd() / ".env", PROJECT_ROOT / ".env")
    for candidate in candidates:
        if candidate and candidate.is_file():
            _load_file(candidate)
            return candidate
    if env_file:
        raise FileNotFoundError(f"Environment file not found: {env_file}")
    return None


def _load_file(path: Path) -> None:
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key.isidentifier():
            raise ValueError(f"Invalid entry in {path} at line {line_number}")
        os.environ.setdefault(key, _clean_value(value))


def _clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value.split(" #", maxsplit=1)[0].rstrip()
