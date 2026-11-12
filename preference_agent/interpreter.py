"""Turn a student's free-text study interests into ranked categories and marks.

For every interest the student gives, each course they can apply for gets two
marks: a match mark from 1 to 10 (how close the course is to the interest) and
a mismatch mark from -1 to -10 (how far off it is: -1 on topic, -10 nothing to
do with it). Their sum is the net mark (-9 to +9).

* ``LLMInterpreter`` makes one OpenAI call (Responses API, strict JSON schema):
  the student's words and the courses to mark in; an ordered list of
  interests, each with category ids, any course the student named, and a
  1-10 mark per course, out. Only known ids and codes are accepted.
* ``KeywordInterpreter`` does the same offline: synonyms and typo tolerance
  for the interests, and the reviewed category marks in
  data/course_categories.json for the course marks. It is the fallback when
  there is no API key or the call fails, and what the tests use.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .categories import CATEGORIES, CATEGORY_BY_ID, CourseTags, relatedness

DEFAULT_MODEL = "gpt-4o-mini"
NO_PREFERENCE = {"anything", "any", "everything", "no preference", "none", "not sure", "dont know",
                 "don't know", "any course", "all"}
FILLER = re.compile(r"\b(i|i'd|id|would|like|love|want|to|study|studying|interested|in|maybe|"
                    r"something|related|with|the|a|an|field|of|do|doing|become|be|career)\b")
SPLIT = re.compile(r"[,;/\n]+|\band\b|\bor\b|\s&\s|\+")


@dataclass
class Preference:
    rank: int
    phrase: str
    categories: list[str]
    courses: list[str] = field(default_factory=list)      # course codes named by the student
    marks: dict[str, int] = field(default_factory=dict)   # course code -> 1..10 closeness to this interest
    mismatches: dict[str, int] = field(default_factory=dict)  # course code -> -1..-10 how far off it is


@dataclass
class Interpretation:
    text: str
    method: str                                            # llm | keywords | none
    preferences: list[Preference] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Interpreter(Protocol):
    def interpret(self, text: str, courses: list[str] | None = None) -> Interpretation: ...


SECOND_CATEGORY_WEIGHT = 0.85


def baseline_mark(tag: CourseTags, pref: Preference) -> int:
    """Mark from the reviewed category marks: a named course is 10; otherwise the
    course's mark in the interest's first category, or a slightly discounted mark
    in its other categories, whichever is higher."""

    if tag.code in pref.courses:
        return 10
    best = 1.0
    for i, category in enumerate(pref.categories):
        best = max(best, tag.mark(category) * (1 if i == 0 else SECOND_CATEGORY_WEIGHT))
    return max(1, min(10, round(best)))


def baseline_mismatch(tag: CourseTags, pref: Preference) -> int:
    """Mismatch from the reviewed marks and category relatedness: -1 when the course
    is on topic, down to -10 when none of its categories is related to the interest.

    fit = best over the course's categories of relatedness(interest, category)
          x (course mark in that category - 1) / 9            (0..1)
    mismatch = -(1 + round(9 x (1 - fit)))
    """

    if tag.code in pref.courses:
        return -1
    fit = 0.0
    for i, wanted in enumerate(pref.categories):
        weight = 1 if i == 0 else SECOND_CATEGORY_WEIGHT
        for category, mark in tag.marks.items():
            fit = max(fit, weight * relatedness(wanted, category) * (mark - 1) / 9)
    return -(1 + round(9 * (1 - min(1.0, fit))))


def fill_marks(result: Interpretation, courses: list[str] | None, tags: dict[str, CourseTags]) -> Interpretation:
    missing = 0
    for pref in result.preferences:
        given = {c: m for c, m in pref.marks.items() if c in tags}
        given_mismatch = {c: m for c, m in pref.mismatches.items() if c in tags}
        marks, mismatches = {}, {}
        for code in dict.fromkeys(c for c in courses or [] if c in tags):
            if code in pref.courses:
                marks[code], mismatches[code] = 10, -1
                continue
            if code in given:
                marks[code] = given[code]
            else:
                marks[code] = baseline_mark(tags[code], pref)
                missing += 1
            if code in given_mismatch:
                mismatches[code] = given_mismatch[code]
            else:
                mismatches[code] = baseline_mismatch(tags[code], pref)
                missing += code in given             # count a course once
        pref.marks, pref.mismatches = marks, mismatches
    if missing and result.method == "llm":
        result.notes.append(f"{missing} course marks were missing from the LLM answer; "
                            "used the reviewed category marks for them")
    return result


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&+ ]", " ", text.casefold().replace("'", ""))).strip()


class KeywordInterpreter:
    """Offline: synonyms, category and course names, with typo tolerance."""

    def __init__(self, tags: dict[str, CourseTags]) -> None:
        self.tags = tags
        self.lexicon: dict[str, str] = {}
        for cat in CATEGORIES:
            for term in (cat.id.replace("_", " "), cat.name, *cat.synonyms):
                self.lexicon.setdefault(_norm(term), cat.id)
        self.course_names = {_norm(t.name): code for code, t in tags.items()}
        self.broad = {_norm(term) for cat in CATEGORIES for term in (cat.id.replace("_", " "), cat.name,
                                                                     cat.synonyms[0])}

    def _match(self, phrase: str) -> tuple[list[str], list[str]]:
        # a specific course name ("quantity surveying") names that course; a broad category
        # word that is also a course name ("engineering", "medicine") stays a category
        if phrase in self.course_names and phrase not in self.broad:
            code = self.course_names[phrase]
            return [self.tags[code].primary], [code]
        if phrase in self.lexicon:
            return [self.lexicon[phrase]], []
        words = phrase.split()
        found: list[str] = []
        for size in (3, 2, 1):                     # longest synonym first: "quantity surveying" before "surveying"
            for i in range(len(words) - size + 1):
                gram = " ".join(words[i:i + size])
                cat = self.lexicon.get(gram)
                if cat is None and size == 1 and len(gram) >= 4:
                    close = difflib.get_close_matches(gram, list(self.lexicon), n=1, cutoff=0.8)
                    cat = self.lexicon[close[0]] if close else None
                if cat and cat not in found:
                    found.append(cat)
            if found:
                break
        return found, []

    def interpret(self, text: str, courses: list[str] | None = None) -> Interpretation:
        return fill_marks(self._interpret(text), courses, self.tags)

    def _interpret(self, text: str) -> Interpretation:
        result = Interpretation(text=text or "", method="keywords")
        for raw in SPLIT.split(text or ""):
            phrase = _norm(raw)
            if not phrase:
                continue
            if phrase in NO_PREFERENCE:
                result.notes.append(f"'{raw.strip()}': no specific preference")
                continue
            categories, courses = self._match(phrase)
            if not categories:
                stripped = re.sub(r"\s+", " ", FILLER.sub(" ", phrase)).strip()
                if stripped and stripped != phrase:
                    categories, courses = self._match(stripped)
            if categories:
                result.preferences.append(Preference(len(result.preferences) + 1, raw.strip(), categories, courses))
            else:
                result.unmatched.append(raw.strip())
        return result


SYSTEM_PROMPT = """You help Sri Lankan A/L students choose state-university degree programmes.
Map the student's study interests to the fixed categories given, then mark how close each course is
to each interest.
Rules:
- One entry per distinct interest, in the student's order (first = most preferred).
- For each entry give 1-2 category ids, best fit first. Use only the given ids.
- Add course_codes only when the student names or clearly describes a specific programme from "programmes".
- For each entry, give EVERY course in "courses_to_mark" two marks:
  * mark, 1 to 10, how close it is to that interest: 10 = exactly what the student asked for,
    7-9 = strongly related, 4-6 = partly related, 1-3 = barely related.
  * mismatch, -1 to -10, how far off it is: -1 = on topic, -3 = a near miss (similar subjects and skills),
    -6 = a clear miss, -10 = nothing to do with the interest.
  A course can have a low mark and a mild mismatch (for "engineering", Physical Science: mark 2,
  mismatch -3) or a low mark and a strong mismatch (for "engineering", Design: mark 3, mismatch -7;
  Dance: mark 1, mismatch -10).
  Use each course's category_marks as a guide so marks stay consistent, but judge the specific interest:
  for "fashion", Fashion Design is mark 10, mismatch -1, while Architecture is about mark 3, mismatch -6.
- "anything", "not sure" and similar mean no preference: return no entry for them.
- Put words that are not study interests, or that fit no category, in unmatched (copy the student's words).
- Do not invent interests the student did not express."""


def _schema(course_codes: list[str], mark_codes: list[str]) -> dict[str, Any]:
    code_field = {"type": "string", "enum": mark_codes} if mark_codes else {"type": "string"}
    return {
        "type": "object", "additionalProperties": False, "required": ["preferences", "unmatched"],
        "properties": {
            "preferences": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["phrase", "categories", "course_codes", "marks"],
                "properties": {
                    "phrase": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string", "enum": [c.id for c in CATEGORIES]}},
                    "course_codes": {"type": "array", "items": {"type": "string", "enum": course_codes}},
                    "marks": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["course_code", "mark", "mismatch"],
                        "properties": {"course_code": code_field,
                                       "mark": {"type": "integer", "enum": list(range(1, 11))},
                                       "mismatch": {"type": "integer", "enum": list(range(-10, 0))}}}},
                }}},
            "unmatched": {"type": "array", "items": {"type": "string"}},
        },
    }


class LLMInterpreter:
    """One OpenAI Responses call with a strict JSON schema."""

    url = "https://api.openai.com/v1/responses"

    def __init__(self, tags: dict[str, CourseTags], model: str | None = None,
                 api_key: str | None = None, timeout: int = 45) -> None:
        self.tags = tags
        self.model = model or os.getenv("PREFERENCE_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.timeout = timeout

    def request_payload(self, text: str, courses: list[str] | None = None) -> dict[str, Any]:
        mark_codes = sorted(c for c in set(courses or []) if c in self.tags)
        catalogue = {
            "categories": [{"id": c.id, "name": c.name, "covers": c.description} for c in CATEGORIES],
            "programmes": [f"{code}: {t.name}" for code, t in sorted(self.tags.items())],
            "courses_to_mark": [{"code": c, "name": self.tags[c].name, "category_marks": self.tags[c].marks}
                                for c in mark_codes],
            "student_interests": text,
        }
        return {
            "model": self.model, "store": False, "max_output_tokens": 8000,
            "input": [{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": json.dumps(catalogue, ensure_ascii=False)}],
            "text": {"format": {"type": "json_schema", "name": "study_preferences", "strict": True,
                                "schema": _schema(sorted(self.tags), mark_codes)}},
        }

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": "CampusYamu-PreferenceAgent/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc
        for item in body.get("output", []):
            for content in item.get("content", []) if item.get("type") == "message" else []:
                if content.get("type") == "refusal":
                    raise RuntimeError(f"model refused: {content.get('refusal')}")
                if content.get("type") == "output_text":
                    return json.loads(content["text"])
        raise RuntimeError(f"no structured output (status {body.get('status')})")

    def interpret(self, text: str, courses: list[str] | None = None) -> Interpretation:
        return self.parse(text, self._call(self.request_payload(text, courses)), courses)

    def parse(self, text: str, raw: dict[str, Any], courses: list[str] | None = None) -> Interpretation:
        """Validate the model's answer; anything unknown is dropped, not trusted.
        Courses the model did not mark get the reviewed baseline mark."""

        result = Interpretation(text=text, method="llm", model=self.model,
                                unmatched=[str(u) for u in raw.get("unmatched", []) if str(u).strip()])
        for item in raw.get("preferences", []):
            codes = [c for c in item.get("course_codes", []) if c in self.tags]
            categories = [c for c in item.get("categories", []) if c in CATEGORY_BY_ID]
            for code in codes:                      # a named course always brings its own category
                if self.tags[code].primary not in categories:
                    categories.append(self.tags[code].primary)
            marks, mismatches = {}, {}
            for entry in item.get("marks", []):
                if entry.get("course_code") not in self.tags:
                    continue
                try:
                    marks[entry["course_code"]] = max(1, min(10, int(entry.get("mark"))))
                except (TypeError, ValueError):
                    pass
                try:
                    mismatches[entry["course_code"]] = max(-10, min(-1, int(entry.get("mismatch"))))
                except (TypeError, ValueError):
                    pass
            if categories:
                result.preferences.append(Preference(len(result.preferences) + 1,
                                                     str(item.get("phrase", "")).strip(), categories, codes,
                                                     marks, mismatches))
            elif item.get("phrase"):
                result.unmatched.append(str(item["phrase"]))
        return fill_marks(result, courses, self.tags)


class PreferenceInterpreter:
    """LLM when available, keywords otherwise (or when the call fails)."""

    def __init__(self, tags: dict[str, CourseTags], use_llm: bool = True, model: str | None = None) -> None:
        self.keywords = KeywordInterpreter(tags)
        self.llm: LLMInterpreter | None = None
        self.reason = "LLM disabled (--no-llm)"
        if use_llm:
            try:
                self.llm = LLMInterpreter(tags, model=model)
            except RuntimeError as exc:
                self.reason = f"LLM not used: {exc}"

    def interpret(self, text: str, courses: list[str] | None = None) -> Interpretation:
        if not (text or "").strip():
            return Interpretation(text="", method="none")
        if self.llm is not None:
            try:
                return self.llm.interpret(text, courses)
            except (RuntimeError, ValueError, KeyError) as exc:
                result = self.keywords.interpret(text, courses)
                result.notes.append(f"LLM call failed ({exc}); used keyword matching")
                return result
        result = self.keywords.interpret(text, courses)
        result.notes.append(self.reason + "; used keyword matching")
        return result
