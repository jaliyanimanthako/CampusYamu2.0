"""Daily limits per signed-in student on the calls that cost money (settings `limits:`).

    chat                one course chat question (POST /v1/chat)
    ai_recommendations  one recommendations run with use_llm (POST /v1/recommendations)
    research            one web research run (POST /v1/career-outlook/research, or started from the chat)

A call is checked before it runs and counted only when it succeeds, so failed calls do not use up the
day. Days follow Sri Lanka time (limits.timezone). A limit of 0 means no limit. Counts live in the
daily_usage table next to the chat memory. Without sign-in (no user id) nothing is limited.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from campusyamu.core import settings

DEFAULTS = {"chat": 60, "ai_recommendations": 10, "research": 3}
WHAT = {"chat": "chat questions", "ai_recommendations": "AI course searches", "research": "web research runs"}


class DailyLimits:
    def __init__(self, store: Callable[[], Any], limits: dict[str, int] | None = None,
                 timezone: str | None = None) -> None:
        self._store = store                                     # called on use: the store opens lazily
        configured = settings.get("limits", {}) or {}
        self.limits = {a: int(configured.get(a, d)) for a, d in DEFAULTS.items()} if limits is None else limits
        self.tz = ZoneInfo(timezone or configured.get("timezone", "Asia/Colombo"))

    def today(self) -> str:
        return datetime.now(self.tz).date().isoformat()

    def status(self, user_id: str) -> dict[str, dict[str, int]]:
        """{action: {used, limit}} for today."""

        used = self._store().usage(user_id, self.today())
        return {a: {"used": used.get(a, 0), "limit": limit} for a, limit in self.limits.items()}

    def check(self, user_id: str | None, action: str) -> str | None:
        """None when the call may run, else the message for the student."""

        limit = self.limits.get(action, 0)
        if not user_id or limit <= 0:
            return None
        if self._store().usage(user_id, self.today()).get(action, 0) >= limit:
            return f"Daily limit reached: {limit} {WHAT.get(action, action)} a day. Try again tomorrow."
        return None

    def record(self, user_id: str | None, action: str) -> dict[str, int] | None:
        """Count one successful call; returns {used, limit}."""

        if not user_id:
            return None
        return {"used": self._store().add_usage(user_id, action, self.today()), "limit": self.limits.get(action, 0)}
