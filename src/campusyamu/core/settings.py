"""Tunable settings from config/settings.yaml (or the file named by CAMPUSYAMU_SETTINGS).

    from campusyamu.core import settings
    settings.get("ranking.cutoff_weight", 2.5)

Every call site passes its own default, so a missing file or key keeps the
built-in behaviour. Secrets never go here; they stay in .env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import CONFIG_DIR

DEFAULT_FILE = CONFIG_DIR / "settings.yaml"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    path = Path(os.environ.get("CAMPUSYAMU_SETTINGS") or DEFAULT_FILE)
    if not path.is_file():
        return {}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return data


def get(key: str, default: Any = None) -> Any:
    """Dotted lookup, e.g. get("ranking.cutoff_weight", 2.5)."""

    node: Any = load()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def model(role: str, env_var: str, default: str = "gpt-4o-mini") -> str:
    """Model for one role: its own env var, then OPENAI_MODEL, then settings, then the default."""

    return os.getenv(env_var) or os.getenv("OPENAI_MODEL") or get(f"models.{role}", default)
