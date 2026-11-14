"""Read a student's interests with Google's Gemini Decisions API (gemini-decision-1).

A decision model does not write text: it scores fixed options in one pass and
returns calibrated probabilities. The OpenAI interpreter writes a JSON entry
for every course and every interest (thousands of output tokens, 20-40 s);
here every judgement is a closed question, answered in parallel.

The student's text is split into phrases with the keyword splitter, then per phrase:

  p<i>_interest   noul    is it a study interest at all?        no  -> unmatched
  p<i>_category   choice  which of the 17 categories fits?      top 1, plus the 2nd if it is close
  p<i>_course     choice  a specific programme named, or none?  only when clearly named

and per phrase x eligible course (the same two marks the OpenAI prompt asks for):

  p<i>_m_<code>   score   10 levels -> match mark 1..10
  p<i>_x_<code>   score   10 levels -> mismatch -10..-1

The scale and examples are in the shared input (sent once per request), so each
question stays short. All wording lives in campusyamu/prompts/preference.py. Up to 1,000 questions go in one request; more are split
into several requests sent in parallel. Unknown or missing answers fall back to
the reviewed category marks (fill_marks), and a failed call to keyword matching
(PreferenceInterpreter).

    POST https://generativelanguage.googleapis.com/v1beta/decisions   (x-goog-api-key: GEMINI_API_KEY)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from campusyamu.core import settings

from campusyamu.prompts import preference as prompts

from .categories import CATEGORIES, CourseTags

DECISIONS_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
DEFAULT_DECISION_MODEL = "gemini-decision-1"
MAX_QUESTIONS = 1000            # per request (API limit)
MAX_PHRASES = 8                 # interests considered from one student
INTEREST_MIN = 0.5              # P(yes) for "is this a study interest"
SECOND_CATEGORY_MIN = settings.get("preferences.decision_second_category_min", 0.25)
NAMED_COURSE_MIN = settings.get("preferences.decision_named_course_min", 0.6)


def decision_model() -> str:
    return settings.model("preference_decision", DEFAULT_DECISION_MODEL)


def call_decisions(payload: dict[str, Any], api_key: str, timeout: int = 60, url: str = DECISIONS_URL,
                   user_agent: str = "CampusYamu-PreferenceDecision/0.1") -> dict[str, Any]:
    """One Gemini Decisions request (also used by the chat's scope check, campusyamu.web.guardrail)."""

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json", "User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini Decisions HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini Decisions request failed: {exc.reason}") from exc
    if not isinstance(body.get("answers"), dict):
        raise RuntimeError(f"Gemini Decisions: no answers in response ({str(body)[:200]})")
    return body


def _fields(tag: CourseTags) -> str:
    return ", ".join(f"{cat} {mark}" for cat, mark in sorted(tag.marks.items(), key=lambda kv: -kv[1])) or "none"


class GeminiDecisionInterpreter:
    """Same output as LLMInterpreter (an Interpretation), from closed questions instead of generated JSON."""

    def __init__(self, tags: dict[str, CourseTags], model: str | None = None,
                 api_key: str | None = None, timeout: int = 60) -> None:
        self.tags = tags
        self.model = model or decision_model()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.timeout = timeout

    # --- requests -------------------------------------------------------------------------------
    @staticmethod
    def phrases(text: str) -> tuple[list[str], list[str]]:
        """The student's interests in order, and notes for "anything"-style phrases (keyword splitter)."""

        from .interpreter import NO_PREFERENCE, SPLIT, _norm

        phrases, notes = [], []
        for raw in SPLIT.split(text or ""):
            phrase = raw.strip()
            if not _norm(phrase):
                continue
            if _norm(phrase) in NO_PREFERENCE:
                notes.append(f"'{phrase}': no specific preference")
            elif phrase.casefold() not in (p.casefold() for p in phrases):
                phrases.append(phrase)
        if len(phrases) > MAX_PHRASES:
            notes.append(f"only the first {MAX_PHRASES} interests were used")
        return phrases[:MAX_PHRASES], notes

    def questions(self, phrases: list[str], courses: list[str] | None) -> dict[str, dict[str, Any]]:
        categories = {c.id: f"{c.name}: {c.description}" for c in CATEGORIES}
        programmes = {code: t.name for code, t in sorted(self.tags.items())}
        programmes["none"] = prompts.NO_PROGRAMME
        to_mark = [c for c in dict.fromkeys(courses or []) if c in self.tags]
        out: dict[str, dict[str, Any]] = {}
        for i, phrase in enumerate(phrases):
            q = json.dumps(phrase, ensure_ascii=False)
            out[f"p{i}_interest"] = {
                "type": "noul", "instructions": prompts.interest_question(q),
                "criteria": {"true_description": prompts.INTEREST_TRUE, "false_description": prompts.INTEREST_FALSE}}
            out[f"p{i}_category"] = {"type": "choice", "instructions": prompts.category_question(q),
                                     "criteria": categories}
            out[f"p{i}_course"] = {"type": "choice", "instructions": prompts.programme_question(q),
                                   "criteria": programmes}
            for code in to_mark:
                tag = self.tags[code]
                course = f'"{tag.name}" (fields: {_fields(tag)})'
                out[f"p{i}_m_{code}"] = {"type": "score", "criteria": prompts.MARK_LEVELS,
                                         "instructions": prompts.mark_question(course, q)}
                out[f"p{i}_x_{code}"] = {"type": "score", "criteria": prompts.MISMATCH_LEVELS,
                                         "instructions": prompts.mismatch_question(course, q)}
        return out

    def request_payloads(self, text: str, courses: list[str] | None = None) -> list[dict[str, Any]]:
        phrases, _ = self.phrases(text)
        items = list(self.questions(phrases, courses).items())
        return [{"model": self.model, "input": prompts.DECISION_GUIDE + text.strip(),
                 "questions": dict(items[start:start + MAX_QUESTIONS])}
                for start in range(0, len(items), MAX_QUESTIONS)]

    # --- calling and reading --------------------------------------------------------------------
    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        return call_decisions(payload, self.api_key, self.timeout)

    def interpret(self, text: str, courses: list[str] | None = None):
        payloads = self.request_payloads(text, courses)
        answers: dict[str, Any] = {}
        if payloads:
            with ThreadPoolExecutor(max_workers=min(4, len(payloads))) as pool:
                for body in pool.map(self._call, payloads):
                    answers.update(body["answers"])
        return self.parse(text, answers, courses)

    def parse(self, text: str, answers: dict[str, Any], courses: list[str] | None = None):
        """Turn answers into an Interpretation; anything missing or unknown is dropped, not trusted."""

        from .interpreter import Interpretation, Preference, fill_marks

        phrases, notes = self.phrases(text)
        result = Interpretation(text=text, method="llm", model=self.model, notes=notes)
        known = {c.id for c in CATEGORIES}
        for i, phrase in enumerate(phrases):
            interest = answers.get(f"p{i}_interest") or {}
            if float(interest.get("noul", 0.0)) < INTEREST_MIN:
                result.unmatched.append(phrase)
                continue
            ranked = sorted(((p, c) for c, p in ((answers.get(f"p{i}_category") or {}).get("probabilities")
                                                 or {}).items() if c in known), reverse=True)
            categories = [c for p, c in ranked[:2] if c == ranked[0][1] or p >= SECOND_CATEGORY_MIN]
            course = answers.get(f"p{i}_course") or {}
            named = course.get("choice")
            codes = [named] if (named in self.tags
                                and float((course.get("probabilities") or {}).get(named, 0)) >= NAMED_COURSE_MIN) else []
            for code in codes:                      # a named course always brings its own category
                if self.tags[code].primary not in categories:
                    categories.append(self.tags[code].primary)
            if not categories:
                result.unmatched.append(phrase)
                continue
            marks, mismatches = {}, {}
            for code in self.tags:
                m, x = answers.get(f"p{i}_m_{code}"), answers.get(f"p{i}_x_{code}")
                if m and m.get("score") is not None:
                    marks[code] = max(1, min(10, round(float(m["score"])) + 1))       # level 0..9 -> 1..10
                if x and x.get("score") is not None:
                    mismatches[code] = max(-10, min(-1, round(float(x["score"])) - 10))  # 0..9 -> -10..-1
            result.preferences.append(Preference(len(result.preferences) + 1, phrase, categories, codes,
                                                 marks, mismatches))
        return fill_marks(result, courses, self.tags)
