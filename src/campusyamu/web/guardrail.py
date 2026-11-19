"""Scope check for the course chat: answer only questions about the course and the university selection
process, nothing from other domains.

Per question, before the answer is written (CourseChat.ask):

  1. obvious manipulation phrases ("ignore previous instructions", "system prompt", ...) are refused at
     once, with no model call;
  2. one Gemini Decision question (gemini-decision-1, GEMINI_API_KEY) scores the latest message, with the
     last turns for context, as in_scope / out_of_scope / manipulation (calibrated probabilities). It runs
     in parallel with the memory recall, the follow-up rewrite and the handbook search, so it adds little
     waiting time;
  3. if P(in_scope) is below guardrail.allow_min the chat returns the fixed refusal (status out_of_scope):
     no answer call, no research, and the turn is not saved to memory.

Fails open, like the AEE Week 13 guardrail: if the check is off (guardrail.enabled false, no
GEMINI_API_KEY) or the call fails, the message goes on, and the chat prompt's own scope rules (the second
layer) still apply. Prompts: campusyamu/prompts/guardrail.py.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from campusyamu.core import settings
from campusyamu.prompts import guardrail as prompts

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-decision-1"
ALLOW_MIN = settings.get("guardrail.allow_min", 0.4)
CONTEXT_TURNS = 4                    # earlier messages shown to the check, for follow-ups
MANIPULATION = re.compile(
    r"\b(ignore|disregard|forget|override)\s+(all\s+|any\s+)?(of\s+)?(your|(the\s+)?(previous|prior|above|earlier))"
    r"\s+(instructions?|rules?|prompts?|guidelines?|directions?)\b"
    r"|\b(system|hidden|initial|developer)\s+(prompt|instructions?|message)\b"
    r"|\b(reveal|show|print|repeat|leak)\b.{0,20}\b(your|the)\s+(prompt|instructions?)\b"
    r"|\bdeveloper\s+mode\b|\bjailbreak\b|\bdo\s+anything\s+now\b|\bDAN\s+mode\b"
    r"|\byou\s+are\s+(now\s+)?no\s+longer\b|\bact\s+as\s+an?\s+(unrestricted|uncensored|unfiltered)\b",
    re.IGNORECASE)


def guardrail_model() -> str:
    return settings.model("guardrail", DEFAULT_MODEL)


@dataclass
class Verdict:
    verdict: str                     # in_scope | out_of_scope | manipulation
    method: str                      # decision | pattern | off | error
    p_in_scope: float | None = None
    ms: int = 0

    @property
    def blocked(self) -> bool:
        return self.verdict != "in_scope"


class ScopeGuard:
    def __init__(self, api_key: str | None = None, model: str | None = None, enabled: bool | None = None,
                 allow_min: float = ALLOW_MIN, caller: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                 timeout: int = 15) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.model = model or guardrail_model()
        self.enabled = settings.get("guardrail.enabled", True) if enabled is None else enabled
        self.allow_min, self.timeout, self._caller = allow_min, timeout, caller

    @property
    def active(self) -> bool:
        return bool(self.enabled and (self.api_key or self._caller))

    @staticmethod
    def pattern(question: str) -> bool:
        """True for obvious attempts to change or reveal the instructions."""

        return bool(MANIPULATION.search(question or ""))

    def payload(self, question: str, course: dict[str, Any], turns: list[dict[str, str]]) -> dict[str, Any]:
        earlier = "\n".join(f"{'student' if t.get('role') == 'user' else 'advisor'}: "
                            f"{' '.join(str(t.get('content', '')).split())[:400]}" for t in turns[-CONTEXT_TURNS:])
        context = (f"Course chat: {course.get('course_name') or course.get('course_code')} ({course.get('uni_code')}) "
                   f"at {course.get('university') or 'a Sri Lankan state university'}.\n"
                   f"Earlier conversation (most recent last):\n{earlier or '(none)'}\n\n"
                   f"Latest student message: {json.dumps(question, ensure_ascii=False)}")
        return {"model": self.model, "input": prompts.SCOPE_GUIDE + context,
                "questions": {"scope": {"type": "choice", "instructions": prompts.SCOPE_QUESTION,
                                        "criteria": prompts.SCOPE_CHOICES}}}

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._caller is not None:
            return self._caller(payload)
        from campusyamu.agents.preference.decision import call_decisions

        return call_decisions(payload, self.api_key, self.timeout, user_agent="CampusYamu-Guardrail/0.1")

    def check(self, question: str, course: dict[str, Any], turns: list[dict[str, str]] | None = None) -> Verdict:
        start = time.perf_counter()
        if self.pattern(question):
            return Verdict("manipulation", "pattern", 0.0)
        if not self.active:
            return Verdict("in_scope", "off")
        try:
            answer = (self._call(self.payload(question, course, turns or [])).get("answers") or {}).get("scope") or {}
            probabilities = {k: float(v) for k, v in (answer.get("probabilities") or {}).items()}
        except Exception as exc:                                # fail open: the chat prompt still has rules
            log.warning("scope check failed (letting the message through): %s", exc)
            return Verdict("in_scope", "error", ms=int((time.perf_counter() - start) * 1000))
        ms = int((time.perf_counter() - start) * 1000)
        if "in_scope" not in probabilities:                     # unreadable answer: let it through
            return Verdict("in_scope", "error", ms=ms)
        p_in = probabilities["in_scope"]
        if p_in >= self.allow_min:
            return Verdict("in_scope", "decision", p_in, ms)
        worst = max((k for k in probabilities if k != "in_scope"), key=probabilities.get, default="out_of_scope")
        return Verdict(worst if worst in prompts.SCOPE_CHOICES else "out_of_scope", "decision", p_in, ms)


def main(argv: list[str] | None = None) -> int:
    """Try the scope check:  uv run python -m campusyamu.web.guardrail "question" ["question" ...]"""

    import argparse

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    parser = argparse.ArgumentParser(prog="python -m campusyamu.web.guardrail", description=main.__doc__)
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--course", default="Engineering")
    parser.add_argument("--university", default="University of Moratuwa")
    args = parser.parse_args(argv)
    _load_env(None)
    guard = ScopeGuard()
    print(f"model {guard.model}, allow_min {guard.allow_min}, " + ("on" if guard.active else "OFF (no GEMINI_API_KEY)"))
    course = {"course_name": args.course, "university": args.university, "uni_code": "-"}
    for question in args.questions:
        v = guard.check(question, course)
        p = "-" if v.p_in_scope is None else f"{v.p_in_scope:.2f}"
        print(f"{'REFUSE' if v.blocked else 'allow ':6}  {v.verdict:<13} p_in_scope={p:<5} {v.method:<8} {v.ms:>5} ms  {question}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
