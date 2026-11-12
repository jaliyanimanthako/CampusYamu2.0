"""Guardrails: what the loop checks before acting and before accepting an answer."""

from __future__ import annotations

from typing import Protocol

from .model import ToolCall


class Guardrails(Protocol):
    def check_call(self, call: ToolCall) -> str | None:
        """Return a reason to refuse this tool call, or None to allow it."""

    def check_finish(self, answer: str) -> list[str]:
        """Return the problems that block this final answer; empty to accept.

        Blocking problems are only those the agent can still fix: once the
        retries or the search budget for a gap are used up, the gap is reported
        honestly in the result instead of blocking forever.
        """

    def final_status(self) -> str:
        """'satisfied' when every check passed, otherwise 'partial'."""

    def open_gaps(self) -> list[str]:
        """Everything still missing, blocking or not, for the honest report."""

    def state_note(self) -> str:
        """Authoritative progress summary, kept across context compaction."""
