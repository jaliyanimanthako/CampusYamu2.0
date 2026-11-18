"""Tunable settings from config/settings.yaml (or the file named by CAMPUSYAMU_SETTINGS).

    from campusyamu.core import settings
    settings.get("ranking.cutoff_weight", 2.5)

Every call site passes its own default, so a missing file or key keeps the
built-in behaviour. Models, engines and other choices live only here (never in
.env); secrets and connection strings stay in .env. For a different setup per
environment (e.g. staging), point CAMPUSYAMU_SETTINGS at another file.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import CONFIG_DIR

DEFAULT_FILE = CONFIG_DIR / "settings.yaml"

# .env variables that used to choose models or settings; they are ignored now
LEGACY_ENV = {
    "OPENAI_MODEL": "models.openai.*", "PREFERENCE_MODEL": "models.<provider>.preference", "FEEDBACK_MODEL": "models.<provider>.feedback",
    "CHAT_MODEL": "models.<provider>.chat", "WEBSITE_MODEL": "models.<provider>.website", "MEMORY_MODEL": "models.<provider>.memory",
    "PREFERENCE_DECISION_MODEL": "models.preference_decision", "GUARDRAIL_MODEL": "models.guardrail",
    "HANDBOOK_EXTRACTION_MODEL": "models.<provider>.handbook_extraction", "AGENT_MODEL": "models.<provider>.career_agent",
    "DISCOVERY_MODEL": "models.<provider>.career_discovery", "PREFERENCE_ENGINE": "preferences.engine",
    "SEARCH_PROVIDER": "career.search_provider", "TAVILY_SEARCH_DEPTH": "career.tavily_search_depth",
    "APIFY_REDDIT_ACTOR": "career.reddit_actor",
}
_warned = False


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


def model(role: str, default: str | None = None, provider: str | None = None) -> str:
    """The model for one role.

    models.<provider>.<role> for the provider in llm.provider (openai | gemini | openrouter), else a top-level
    models.<role> (roles tied to one service, e.g. the Gemini Decision guardrail), else the default,
    else the provider's default model. `provider` asks about one provider instead of the configured one.
    """

    from . import llm

    warn_legacy_env()
    name = provider or llm.provider()
    for key in (f"models.{name}.{role}", f"models.{role}"):
        value = get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default or llm.DEFAULT_MODELS[name]


def warn_legacy_env() -> None:
    """Once per process: say which old .env choices are set but no longer used."""

    global _warned
    if _warned:
        return
    _warned = True
    old = [f"{name} (now {LEGACY_ENV[name]})" for name in LEGACY_ENV if os.getenv(name)]
    if old:
        logging.getLogger(__name__).warning("ignored in .env, set in config/settings.yaml instead: %s",
                                            ", ".join(old))
