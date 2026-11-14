"""Feedback on order 3: a summary, a note per course and "if you care more about..." advice.

* ``TemplateFeedback`` writes it from the what-if facts with fixed sentences
  (offline, deterministic; the fallback and what the tests use).
* ``LLMFeedback`` sends the same facts to OpenAI once (strict JSON schema) and
  gets back friendlier wording. It may only refer to the courses it was given;
  unknown codes are dropped, and any course it skips gets the template note.
* ``FeedbackWriter`` picks the LLM when a key is set, else the template.
"""

from __future__ import annotations

import json
import os
from typing import Any

from campusyamu.core import settings

from campusyamu.core.openai_client import call_structured

from .sensitivity import PROFILE_LABELS
from campusyamu.prompts.feedback import FEEDBACK_SYSTEM as SYSTEM_PROMPT

DEFAULT_MODEL = "gpt-4o-mini"
MAX_NOTE_CHARS = 320
WHAT_IF = [p for p in PROFILE_LABELS if p != "balanced"]
STRENGTH_TEXT = {"interest": "it fits your interests", "cutoff": "it is a high-demand course (high cut-off)",
                 "distance": "it is close to home"}
WEAKNESS_LABELS = {"interest": "a weaker match with your interests", "cutoff": "a lower cut-off",
                   "distance": "the distance from home"}
BAND_TEXT = {"strong": "your Z-score is at or above recent cut-offs",
             "competitive": "your Z-score is close to the cut-off",
             "reach": "your Z-score is a little below the estimated cut-off (ambitious)",
             "unlikely": "your Z-score is well below recent cut-offs (very ambitious)"}


def _name(c: dict[str, Any]) -> str:
    return f"{c['course_name']} ({c['university']})"


class TemplateFeedback:
    method = "template"

    def course_note(self, c: dict[str, Any], analysis: dict[str, Any]) -> str:
        t = analysis["thresholds"]
        bits = []
        if c["in_list"]:
            bits.append(f"#{c['balanced_rank']} mainly because {STRENGTH_TEXT[c['strength']]}")
            if c["weakness"]:
                bits[-1] += f"; held back by {WEAKNESS_LABELS[c['weakness']]}"
        else:
            bits.append(f"not in your balanced top {t['list_size']} (#{c['balanced_rank']})")
        if c.get("band") in BAND_TEXT:
            bits.append(BAND_TEXT[c["band"]])
        if c["in_list"] and c["worst_rank"] <= t["safe_top"]:
            bits.append(f"stays in your top {t['safe_top']} whatever you prioritise")
        for profile, move in c["moves"].items():
            rank = c["profile_ranks"][profile]
            if c["in_list"] and rank > t["list_size"]:
                bits.append(f"drops out of the top {t['list_size']} {PROFILE_LABELS[profile]}")
            elif not c["in_list"] and rank <= t["list_size"]:
                bits.append(f"enters at #{rank} {PROFILE_LABELS[profile]}")
            elif abs(move) >= t["notable_move"]:
                bits.append(f"{'rises' if move > 0 else 'falls'} to #{rank} {PROFILE_LABELS[profile]}")
        if c["aptitude_test"]:
            bits.append("needs an aptitude test")
        if c["ol_to_confirm"]:
            bits.append("O/L requirement still to confirm")
        text = "; ".join(bits)
        return text[0].upper() + text[1:] + "."

    def write(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        courses = analysis["courses"]
        listed = [c for c in courses if c["in_list"]]
        by_code = {c["uni_code"]: c for c in courses}
        top3 = listed[:3]
        ambitious = [c for c in top3 if c["band"] in ("reach", "unlikely")]
        strong = sum(c["band"] == "strong" for c in listed)
        summary = (f"Your balanced list has {len(listed)} options: {strong} strong by last year's cut-offs, "
                   f"{len(listed) - strong} competitive or ambitious. ")
        if ambitious:
            summary += (f"{len(ambitious)} of your top 3 are ambitious ({', '.join(c['band'] for c in ambitious)}), "
                        "so keep strong options further down. ")
        if analysis["safe_picks"]:
            summary += (f"{len(analysis['safe_picks'])} stay in your top {analysis['thresholds']['safe_top']} "
                        "whatever you prioritise.")
        priorities = []
        for profile in WHAT_IF:
            up = sorted((c for c in listed if c["moves"][profile] >= analysis["thresholds"]["notable_move"]),
                        key=lambda c: -c["moves"][profile])[:3]
            new = [by_code[code] for code in analysis["risers"].get(profile, [])][:3]
            down = sorted((c for c in listed if c["moves"][profile] <= -analysis["thresholds"]["notable_move"]),
                          key=lambda c: c["moves"][profile])[:3]
            parts = []
            if up:
                parts.append("rises: " + ", ".join(f"{_name(c)} to #{c['profile_ranks'][profile]}" for c in up))
            if new:
                parts.append("new in your list: " + ", ".join(f"{_name(c)} at #{c['profile_ranks'][profile]}"
                                                               for c in new))
            if down:
                parts.append("falls: " + ", ".join(f"{_name(c)} to #{c['profile_ranks'][profile]}" for c in down))
            advice = ("; ".join(parts) if parts else "the order barely changes") + "."
            priorities.append({"profile": profile, "label": PROFILE_LABELS[profile],
                               "advice": advice[0].upper() + advice[1:]})
        close = [{**cc, "note": (f"#{cc['ranks'][0]} and #{cc['ranks'][1]} are almost tied"
                                 if len(cc["uni_codes"]) == 2 else
                                 f"#{cc['ranks'][0]}–#{cc['ranks'][1]} are nearly tied")
                                + f" (within {cc['spread']:.2f} points); order them by what you prefer."}
                 for cc in analysis["close_calls"]]
        cautions = []
        if listed and all(c["band"] in ("reach", "unlikely") for c in listed[:10]):
            cautions.append("None of your top 10 is a strong option by last year's cut-offs.")
        return {"method": self.method, "summary": summary.strip(),
                "course_notes": {c["uni_code"]: {"note": self.course_note(c, analysis), "source": "template"}
                                 for c in courses},
                "priorities": [{**p, "source": "template"} for p in priorities],
                "close_calls": close, "cautions": cautions, "notes": []}



class LLMFeedback:
    method = "llm"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: int = 90) -> None:
        self.model = model or settings.model("feedback", "FEEDBACK_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.timeout = timeout
        self.template = TemplateFeedback()

    def request_payload(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        codes = [c["uni_code"] for c in analysis["courses"]]
        facts = {
            "student": context,
            "what_if_profiles": {p: {"meaning": PROFILE_LABELS[p], "weights": analysis["profiles"][p]}
                                 for p in analysis["profiles"]},
            "score_parts": {"interest": "preference score (-9..+9)", "cutoff": "2.5 x last-year cut-off",
                            "distance": "travel penalty (0 = nearest site)"},
            "thresholds": analysis["thresholds"],
            "courses": analysis["courses"],
            "safe_picks": analysis["safe_picks"],
            "close_calls": analysis["close_calls"],
        }
        code = {"type": "string", "enum": codes}
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["summary", "course_notes", "priorities", "close_calls", "cautions"],
            "properties": {
                "summary": {"type": "string"},
                "course_notes": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["uni_code", "note"],
                    "properties": {"uni_code": code, "note": {"type": "string"}}}},
                "priorities": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["profile", "advice"],
                    "properties": {"profile": {"type": "string", "enum": WHAT_IF}, "advice": {"type": "string"}}}},
                "close_calls": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["uni_codes", "note"],
                    "properties": {"uni_codes": {"type": "array", "items": code}, "note": {"type": "string"}}}},
                "cautions": {"type": "array", "items": {"type": "string"}},
            },
        }
        return {"model": self.model, "store": False, "max_output_tokens": 8000,
                "input": [{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": json.dumps(facts, ensure_ascii=False, default=str)}],
                "text": {"format": {"type": "json_schema", "name": "order_feedback", "strict": True,
                                    "schema": schema}}}

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        return call_structured(payload, self.api_key, self.timeout, "CampusYamu-RankingFeedback/0.1")

    def write(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return self.parse(self._call(self.request_payload(analysis, context)), analysis, context)

    def parse(self, raw: dict[str, Any], analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Keep only what refers to known courses/profiles; fill gaps from the template."""

        fallback = self.template.write(analysis, context)
        known = {c["uni_code"] for c in analysis["courses"]}
        notes = dict(fallback["course_notes"])
        given = 0
        for item in raw.get("course_notes", []):
            text = " ".join(str(item.get("note", "")).split())[:MAX_NOTE_CHARS]
            if item.get("uni_code") in known and text:
                notes[item["uni_code"]] = {"note": text, "source": "llm"}
                given += 1
        advice = {p["profile"]: " ".join(str(p.get("advice", "")).split())[:2 * MAX_NOTE_CHARS]
                  for p in raw.get("priorities", []) if p.get("profile") in WHAT_IF and p.get("advice")}
        priorities = [({"profile": p["profile"], "label": p["label"], "advice": advice[p["profile"]], "source": "llm"}
                       if p["profile"] in advice else p) for p in fallback["priorities"]]
        close_notes = {tuple(c.get("uni_codes", [])): str(c.get("note", "")).strip()
                       for c in raw.get("close_calls", [])}
        close = [{**cc, "note": close_notes.get(tuple(cc["uni_codes"])) or cc["note"]} for cc in fallback["close_calls"]]
        result = {
            "method": self.method, "model": self.model,
            "summary": " ".join(str(raw.get("summary", "")).split()) or fallback["summary"],
            "course_notes": notes, "priorities": priorities, "close_calls": close,
            "cautions": [" ".join(str(c).split()) for c in raw.get("cautions", []) if str(c).strip()][:6],
            "notes": [],
        }
        missing = len(known) - given
        if missing:
            result["notes"].append(f"{missing} course note(s) missing from the LLM answer; used template notes")
        return result


class FeedbackWriter:
    """LLM when available, template otherwise (or when the call fails)."""

    def __init__(self, use_llm: bool = True, model: str | None = None) -> None:
        self.template = TemplateFeedback()
        self.llm: LLMFeedback | None = None
        self.reason = "LLM disabled (--no-llm)"
        if use_llm:
            try:
                self.llm = LLMFeedback(model=model)
            except RuntimeError as exc:
                self.reason = f"LLM not used: {exc}"

    def write(self, analysis: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if not analysis.get("courses"):
            return {"method": "none", "summary": "", "course_notes": {}, "priorities": [], "close_calls": [],
                    "cautions": [], "notes": ["nothing to explain (no interests or no ranked options)"]}
        if self.llm is not None:
            try:
                return self.llm.write(analysis, context)
            except (RuntimeError, ValueError, KeyError) as exc:
                result = self.template.write(analysis, context)
                result["notes"].append(f"LLM call failed ({exc}); used template feedback")
                return result
        result = self.template.write(analysis, context)
        result["notes"].append(self.reason + "; used template feedback")
        return result
