"""Parse handbook prose and optionally propose schema-constrained A/L rules."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from campusyamu.core.paths import OWNER_INTERPRETATIONS as OWNER_INTERPRETATIONS_PATH

from .al_clause_parsers import canonical_subject, normalize_clause, parse_al_clause
from .al_clause_parsers import AL_SUBJECTS, STREAM_ALIASES, SUBJECT_ALIASES, canonical_stream
from .al_rule_semantics import (
    NotEvaluable,
    Student,
    equivalent_rule_sets,
    evaluate_rules,
    normalize_subject_list,
)
from .name_normalization import lookup_key, stable_slug
from .source_registry import PROJECT_ROOT, file_sha256
from campusyamu.prompts.handbook import rule_extraction_prompt


SCHEMA_VERSION = 2
DEFAULT_GRAPH_DATA = Path("data/processed/knowledge_graph/normalized_graph_data.json")
DEFAULT_STRUCTURE = Path("data/processed/knowledge_graph/handbook_structure.json")
DEFAULT_REQUESTS = Path("data/processed/knowledge_graph/al_extraction_requests.json")
OWNER_INTERPRETATIONS = (
    OWNER_INTERPRETATIONS_PATH
)
DEFAULT_PROPOSALS = Path("data/processed/knowledge_graph/al_rule_proposals.json")
DEFAULT_VALIDATION = Path("data/processed/knowledge_graph/al_rule_validation_report.json")
DEFAULT_REVIEW_QUEUE = Path("data/processed/knowledge_graph/al_review_queue.json")
STRUCTURED_SOURCE_ID = "structured-handbook"

PAGE_MARKER_RE = re.compile(r"^<!-- PDF page (\d+) -->$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SECTION_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)+)\b")
COURSE_SECTION_RE = re.compile(r"^(2\.2\.\d+\.\d+)\b")
STREAM_SECTION_RE = re.compile(r"^(2\.2\.(\d+))\b")
COURSE_CODE_RE = re.compile(r"\b(\d{3})\b")
ARTS_INTERNAL_BLOCK_RE = re.compile(
    r"^\*\*\s*(\d+)\.\s+.*\bCourses? of Study\b",
    re.IGNORECASE,
)
ARTS_GENERAL_SUBBLOCKS = (
    ("basket-1", re.compile(r"^##### Basket 01\b", re.IGNORECASE)),
    ("basket-2", re.compile(r"^##### Basket 02\b", re.IGNORECASE)),
    ("basket-3", re.compile(r"^##### Basket 03\b", re.IGNORECASE)),
    ("basket-4", re.compile(r"^##### Basket 04\b", re.IGNORECASE)),
    (
        "cross-basket-exceptions",
        re.compile(r"^##### Exemptions are;", re.IGNORECASE),
    ),
)
SHARED_GUIDANCE_RE = re.compile(
    r"\b(?:the\s+)?above[ -]mentioned courses? of study\b",
    re.IGNORECASE,
)
OL_EVIDENCE_RE = re.compile(
    r"G\.C\.E\.\s*\(Ordinary Level\)|Ordinary Level Examination",
    re.IGNORECASE,
)
AL_EVIDENCE_RE = re.compile(
    r"G\.C\.E\.\s*\(Advanced Level\)|Advanced Level Examination",
    re.IGNORECASE,
)
APTITUDE_EVIDENCE_RE = re.compile(
    r"\bAptitude Tests?\b|\bPractical Tests?\b", re.IGNORECASE
)
DESCRIPTIVE_EVIDENCE_RE = re.compile(
    r"\bIn the final year\b|\bindustrial training\b|"
    r"\bdegree programmes? (?:are|is) offered\b|"
    r"\bcould also seek admission to the following\b",
    re.IGNORECASE,
)
OTHER_ACADEMIC_YEAR_RE = re.compile(
    r"\bfrom the academic year\s+(\d{4})\s*/\s*\d{2,4}", re.IGNORECASE
)
OR_SEPARATOR_RE = re.compile(
    r"^[-*\s]*(?:\*\*|<sup>)?\s*or\s*(?:\*\*|</sup>)?\s*$", re.IGNORECASE
)
AND_SEPARATOR_RE = re.compile(r"^[-*\s]*(?:\*\*)?\s*and\s*(?:\*\*)?\s*$", re.IGNORECASE)
REQUIREMENT_END_RE = re.compile(
    r"^#|"
    r"^[-*]?\s*(?:\*\*)?\s*(?:Degree Programmes?|Available|Duration|Medium|Location|"
    r"Fields? of|:)|"
    r"\b(?:is|are) available\b|\bavailable in\b|\bDuration\b|"
    r"degree programmes? (?:offered|available)|medium of instructions?\b|"
    r"\bAptitude Tests?\b|\bPractical Tests?\b|"
    r"^\d+\.\s+(?:University|.*\bCampus\b|.*\bInstitute\b)|"
    r"^\d{1,3}% of the (?:total|proposed intake)\b|"
    r"Candidates are required to submit|press notice|Please visit|"
    r"\bThese (?:two |three )?requirements are given\b",
    re.IGNORECASE,
)
PROGRAMME_LEVEL_RE = re.compile(r"\bdegree programmes? such as\b", re.IGNORECASE)
PROGRAMME_LIST_RE = re.compile(
    r"Names of the universities and the degree programmes", re.IGNORECASE
)
LIST_INTRO_RE = re.compile(r"\bfollowing\b|[:;]\**$", re.IGNORECASE)
LIST_ITEM_RE = re.compile(
    r"^(?:\((?:[ivx]{1,4}|[a-h])\)|(?:[ivx]{1,4}|[a-h])[).]\s|I{1,3}\s)",
    re.IGNORECASE,
)
SELECTION_PROCESS_EVIDENCE_RE = re.compile(
    r"\b(?:maximum number of students allocated|allocation of students|"
    r"selection (?:is|will be) based on|basis of selection|"
    r"when selecting students|percentage of the intake)\b",
    re.IGNORECASE,
)
CLAUSE_INTRO_RE = re.compile(
    r"(?:"
    r"^[-*\s]*For example\b|"
    r"minimum eligibility requirements for admission\s*:|"
    r"guidance for (?:the )?selection .* (?:is given|given) below|"
    r"(?:fulfill|fulfilled|needed|requirements).*following requir(?:e)?ments|"
    r"required .* (?:are|is) given below|"
    r"one of the following (?:two |three )?categories"
    r")",
    re.IGNORECASE,
)
CATEGORY_HEADING_RE = re.compile(r"^#+\s*Category\s*\(?[A-Z]\)?\s*$", re.IGNORECASE)
ELIGIBILITY_SIGNAL_RE = re.compile(
    r"\b(?:"
    r"must|should|eligible|eligibility|minimum|at least|"
    r"not more than|maximum|maxim(?:um|ally)|cannot|can (?:also )?select|need not|"
    r"no (?:candidate|student)|allowed|pass(?:es)?|obtained|subject to"
    r")\b",
    re.IGNORECASE,
)

CLAUSE_DISPOSITIONS = (
    "extracted",
    "intentionally_ignored",
    "needs_review",
)
CLAUSE_IGNORE_REASONS = (
    "ordinary_level_requirement",
    "programme_level_requirement",
    "cross_level_alternative",
    "other_academic_year",
    "aptitude_test_requirement",
    "duration_medium_or_intake",
    "selection_process_only",
    "descriptive_not_eligibility",
    "not_ignored",
)

DETERMINISTIC_ARTS_UNITS = {
    "general-core",
    "basket-1",
    "basket-2",
    "basket-3",
    "basket-4",
    "cross-basket-exceptions",
}

# One anchor phrase per clause, in ledger order. Specs in
# _deterministic_arts_specs are index-based, so this guards against a clause
# shifting position (e.g. after a detector change) while the count stays equal.
DETERMINISTIC_ARTS_ANCHORS = {
    "general-core": ("at least ‘S’ grades for three subjects", "passes in three subjects"),
    "basket-1": (
        "at least one subject from this basket",
        "all three subjects only from basket 01",
        "three National Languages",
        "combination of National and Classical languages",
        "no candidate can select three classical languages",
        "two languages from the basket 04",
    ),
    "basket-2": (
        "maximum of two subjects from the basket 02",
        "related civilization of the selected religion",
    ),
    "basket-3": ("two subjects from one subject area",),
    "basket-4": ("maximum of two subjects from this basket",),
    "cross-basket-exceptions": (
        "can select three National Languages",
        "two subjects from Classical Languages",
        "three Classical Languages or three Foreign Languages",
    ),
}

EXPECTED_IGNORE_REASON = {
    "excluded_ordinary_level": "ordinary_level_requirement",
    # An O/L requirement that may alternatively be met with an A/L grade
    # (e.g. "C in O/L Mathematics or S in A/L Mathematics"). Kept out of A/L
    # rule extraction but tracked separately so the O/L requirement node can
    # carry the A/L alternative instead of silently losing it.
    "excluded_cross_level_alternative": "cross_level_alternative",
    "excluded_aptitude_test": "aptitude_test_requirement",
    # A requirement for named degree programmes inside a course ("degree
    # programmes such as Accountancy ... should have offered Accounting", or a
    # footnote in the university/programme list), not for the whole course.
    # Captured separately as a programme-level requirement.
    "excluded_programme_level": "programme_level_requirement",
    "excluded_selection_process": "selection_process_only",
    # Programme descriptions such as final-year industrial training.
    "excluded_descriptive": "descriptive_not_eligibility",
    # Requirements announced for a later intake (e.g. Law from 2025/2026).
    "excluded_other_academic_year": "other_academic_year",
}

STREAM_NAMES = {
    "1": "Arts",
    "2": "Commerce",
    "3": "Biological Science",
    "4": "Physical Science",
    "5": "Engineering Technology",
    "6": "Biosystems Technology",
    "7": "Information Communication Technology",
    "8": "Courses open to multiple subject streams",
}

COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
SUBJECT_COMBINATION_HEADER_RE = re.compile(
    r"^(one|two|three|four|five)\s+subjects?\s+should\s+have\s+(?:been\s+)?offered\s+"
    r"at\s+the\s+G\.C\.E\.\s*\(Advanced Level\)\s+Examination\s+from\s+(.+?)\s+Stream\b"
    r".*\bsubject to the following conditions\.?$",
    re.IGNORECASE,
)
MAXIMUM_COUNT_CLAUSE_RE = re.compile(
    r"^(?:\d+\.\s*)?Not more than\s+(one|two|three|four|five)\s+(.+?)\.?$",
    re.IGNORECASE,
)
FOLLOWING_SUBJECTS_RE = re.compile(r"^of the following subjects:?$", re.IGNORECASE)
SUBJECT_GROUP_PREFIX_RE = re.compile(r"^subjects?\s+from\s+(?:the\s+)?", re.IGNORECASE)
BULLET_ITEM_RE = re.compile(r"^[-*]\s+(.+?)\s*$")

REQUIREMENT_TYPES = (
    "al_subject_combination",
    "al_minimum_grades",
    "al_subject_choice",
    "al_stream_eligibility",
    "al_basket_rule",
    "al_exception",
    "other_admission_requirement",
)


class HandbookProseError(RuntimeError):
    """Raised when handbook structure or model proposals are invalid."""


class ExtractionHarnessError(HandbookProseError):
    """Raised after every guarded correction attempt fails validation."""

    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.model_calls = len(attempts)


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    line_number: int
    pdf_page: int | None
    section_number: str | None
    heading_id: str
    parent_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.heading_id,
            "level": self.level,
            "title": self.title,
            "section_number": self.section_number,
            "parent_id": self.parent_id,
            "markdown_line": self.line_number,
            "pdf_page": self.pdf_page,
        }


class RuleExtractionModel(Protocol):
    model: str

    def extract(
        self,
        request: dict[str, Any],
        schema: dict[str, Any],
        *,
        correction_history: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]: ...


def _section_number(title: str) -> str | None:
    match = SECTION_NUMBER_RE.match(title)
    return match.group(1) if match else None


def _page_map(lines: Sequence[str]) -> tuple[list[dict[str, int]], list[int | None]]:
    markers: list[dict[str, int]] = []
    pages: list[int | None] = [None] * (len(lines) + 1)
    current_page: int | None = None
    for line_number, line in enumerate(lines, start=1):
        match = PAGE_MARKER_RE.match(line)
        if match:
            current_page = int(match.group(1))
            markers.append({"pdf_page": current_page, "markdown_line": line_number})
        pages[line_number] = current_page
    expected = list(range(1, 209))
    actual = [marker["pdf_page"] for marker in markers]
    if actual != expected:
        raise HandbookProseError(
            "Structured handbook must contain sequential PDF page markers 1-208"
        )
    return markers, pages


def _parse_headings(
    lines: Sequence[str], pages: Sequence[int | None]
) -> list[Heading]:
    headings: list[Heading] = []
    stack: list[Heading] = []
    for line_number, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        number = _section_number(title)
        while stack and stack[-1].level >= level:
            stack.pop()
        parent_id = stack[-1].heading_id if stack else None
        if number:
            heading_id = f"section:{number}"
        else:
            heading_id = f"heading:{line_number}:{stable_slug(title) or 'untitled'}"
        heading = Heading(
            level=level,
            title=title,
            line_number=line_number,
            pdf_page=pages[line_number],
            section_number=number,
            heading_id=heading_id,
            parent_id=parent_id,
        )
        headings.append(heading)
        stack.append(heading)
    ids = [heading.heading_id for heading in headings]
    if len(ids) != len(set(ids)):
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        raise HandbookProseError(
            "Duplicate deterministic heading IDs: " + ", ".join(duplicates)
        )
    return headings


def _extract_course_codes(
    section_lines: Sequence[str], known_codes: set[str]
) -> list[str]:
    codes: set[str] = set()
    for line in section_lines:
        lowered = line.casefold()
        marker = lowered.find("course code")
        if marker < 0:
            continue
        segment = line[marker:]
        proposed_marker = segment.casefold().find("proposed intake")
        if proposed_marker >= 0:
            segment = segment[:proposed_marker]
        codes.update(code for code in COURSE_CODE_RE.findall(segment) if code in known_codes)
    return sorted(codes)


def _heading_course_name(title: str) -> str:
    value = COURSE_SECTION_RE.sub("", title, count=1).strip()
    value = re.sub(r"\s*\(Course Code.*$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"^Course of Study in\s+", "", value, flags=re.IGNORECASE)
    value = re.split(r"\s+offered by\s+", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return value.replace("**", "").strip()


def _course_section_headings(headings: Sequence[Heading]) -> list[Heading]:
    result = [
        heading
        for heading in headings
        if heading.section_number
        and (
            COURSE_SECTION_RE.match(heading.section_number)
            or heading.section_number == "2.2.7"
        )
    ]
    if not result:
        raise HandbookProseError("No A/L course sections were discovered")
    return result


def _course_boundaries(headings: Sequence[Heading]) -> list[int]:
    boundaries: set[int] = set()
    for heading in headings:
        number = heading.section_number or ""
        if COURSE_SECTION_RE.match(number):
            boundaries.add(heading.line_number)
        elif re.fullmatch(r"2\.2\.\d+", number):
            boundaries.add(heading.line_number)
        elif number.startswith("3.") or number == "3":
            boundaries.add(heading.line_number)
    return sorted(boundaries)


def _resolve_section_targets(
    heading: Heading,
    section_lines: Sequence[str],
    courses_by_code: dict[str, dict[str, Any]],
    course_lookup: dict[str, str],
) -> list[str]:
    codes = _extract_course_codes(section_lines, set(courses_by_code))
    if codes:
        return [str(courses_by_code[code]["id"]) for code in codes]
    heading_name = _heading_course_name(heading.title)
    target = course_lookup.get(lookup_key(heading_name))
    if target:
        return [target]
    raise HandbookProseError(
        f"Could not resolve a course target for section {heading.section_number}: "
        f"{heading.title}"
    )


def _extraction_unit_ranges(
    heading: Heading,
    start: int,
    end: int,
    lines: Sequence[str],
) -> list[dict[str, Any]]:
    """Split the oversized Arts section into general and internal course blocks."""

    if heading.section_number != "2.2.1.1":
        return [
            {
                "unit_key": None,
                "title": heading.title,
                "start": start,
                "end": end,
            }
        ]

    internal_starts: list[tuple[int, str, str]] = []
    for line_number in range(start, end + 1):
        line = lines[line_number - 1]
        match = ARTS_INTERNAL_BLOCK_RE.match(line)
        if not match:
            continue
        block_number = match.group(1)
        internal_starts.append(
            (
                line_number,
                f"special-{block_number}",
                line.strip("* "),
            )
        )
    if len(internal_starts) != 11:
        raise HandbookProseError(
            "Expected 11 internal course blocks in section 2.2.1.1, "
            f"found {len(internal_starts)}"
        )

    general_end = internal_starts[0][0] - 1
    general_starts: list[tuple[int, str, str]] = [
        (start, "general-core", heading.title)
    ]
    for unit_key, pattern in ARTS_GENERAL_SUBBLOCKS:
        matches = [
            line_number
            for line_number in range(start, general_end + 1)
            if pattern.match(lines[line_number - 1])
        ]
        if len(matches) != 1:
            raise HandbookProseError(
                f"Expected one {unit_key} boundary in section 2.2.1.1, "
                f"found {len(matches)}"
            )
        line_number = matches[0]
        general_starts.append(
            (line_number, unit_key, lines[line_number - 1].lstrip("# "))
        )
    general_starts.sort()

    units: list[dict[str, Any]] = []
    for index, (line_number, unit_key, title) in enumerate(general_starts):
        next_start = (
            general_starts[index + 1][0]
            if index + 1 < len(general_starts)
            else general_end + 1
        )
        units.append(
            {
                "unit_key": unit_key,
                "title": title,
                "start": line_number,
                "end": next_start - 1,
            }
        )
    for index, (line_number, unit_key, title) in enumerate(internal_starts):
        next_start = (
            internal_starts[index + 1][0]
            if index + 1 < len(internal_starts)
            else end + 1
        )
        units.append(
            {
                "unit_key": unit_key,
                "title": title,
                "start": line_number,
                "end": next_start - 1,
            }
        )
    return units


def _clause_scope_hint(text: str, inherited: str | None = None) -> str:
    """Scope a clause from its own wording, falling back to its list context.

    Explicit level wording in the clause always wins. A list item with no level
    wording of its own (e.g. "(a) At least a Credit Pass (C) in English")
    inherits the scope of the intro line that introduced the list.
    """

    if inherited == "excluded_other_academic_year":
        return inherited
    if OL_EVIDENCE_RE.search(text) and AL_EVIDENCE_RE.search(text):
        return "excluded_cross_level_alternative"
    if OL_EVIDENCE_RE.search(text):
        return "excluded_ordinary_level"
    if APTITUDE_EVIDENCE_RE.search(text):
        return "excluded_aptitude_test"
    if SELECTION_PROCESS_EVIDENCE_RE.search(text):
        return "excluded_selection_process"
    if DESCRIPTIVE_EVIDENCE_RE.search(text):
        return "excluded_descriptive"
    if inherited is not None and not AL_EVIDENCE_RE.search(text):
        return inherited
    return "advanced_level_candidate"


def _is_list_item(text: str) -> bool:
    if text.startswith("**"):
        return bool(LIST_ITEM_RE.match(text.lstrip("* ")))
    return text.startswith(("-", "*")) or bool(LIST_ITEM_RE.match(text))


def _other_academic_year(text: str, academic_year: str | None) -> bool:
    match = OTHER_ACADEMIC_YEAR_RE.search(text)
    if match is None or not academic_year:
        return False
    return int(match.group(1)) > int(academic_year.split("/")[0])


def _eligibility_clauses(
    section_id: str,
    evidence_lines: Sequence[dict[str, Any]],
    academic_year: str | None = None,
) -> list[dict[str, Any]]:
    """Create a deterministic ledger of eligibility-like source clauses."""

    clauses: list[dict[str, Any]] = []
    inherited: str | None = None
    other_year = False
    since_last_clause: list[str] = []
    programme_list = False
    for item in evidence_lines:
        text = str(item["text"]).strip()
        if not text or text.startswith("<!--"):
            continue
        since_last_clause.append(text)
        if PROGRAMME_LIST_RE.search(text):
            # Everything after this heading belongs to named programmes.
            programme_list = True
        # Context is tracked on every line, including intro lines that are
        # not clauses themselves ("...following requirements at the G.C.E.
        # (Ordinary Level) Examination;").
        if _other_academic_year(text, academic_year):
            other_year = True
        if not _is_list_item(text):
            inherited = (
                "excluded_ordinary_level"
                if OL_EVIDENCE_RE.search(text)
                and not AL_EVIDENCE_RE.search(text)
                and LIST_INTRO_RE.search(text)
                else None
            )
        if CLAUSE_INTRO_RE.search(text) or not ELIGIBILITY_SIGNAL_RE.search(text):
            continue
        context = "excluded_other_academic_year" if other_year else inherited
        clause = {
            "id": f"{section_id}:clause:{len(clauses) + 1}",
            "text": text,
            "markdown_line_start": int(item["markdown_line"]),
            "markdown_line_end": int(item["markdown_line"]),
            "pdf_page": item["pdf_page"],
            "scope_hint": (
                "excluded_programme_level"
                if programme_list or PROGRAMME_LEVEL_RE.search(text)
                else _clause_scope_hint(text, context)
            ),
            "status": "pending",
        }
        # "(i) <O/L requirement> / or / (ii) <A/L requirement>": sibling list
        # items at different levels joined by an "or" line are one cross-level
        # requirement, not a mandatory A/L rule plus an O/L rule.
        previous = clauses[-1] if clauses else None
        if (
            previous is not None
            and _is_list_item(previous["text"])
            and _is_list_item(text)
            and {previous["scope_hint"], clause["scope_hint"]}
            == {"excluded_ordinary_level", "advanced_level_candidate"}
            and any(OR_SEPARATOR_RE.match(line) for line in since_last_clause[:-1])
        ):
            previous["scope_hint"] = "excluded_cross_level_alternative"
            clause["scope_hint"] = "excluded_cross_level_alternative"
        clauses.append(clause)
        since_last_clause = []
    return clauses


def parse_handbook_structure(
    markdown_text: str,
    graph_data: dict[str, Any],
    *,
    source_path: str,
    source_checksum: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse page markers, headings, streams, and bounded A/L course sections."""

    if graph_data.get("generation_stage") != "name_normalization":
        raise HandbookProseError("Expected normalized graph data as input")
    lines = markdown_text.splitlines()
    page_markers, pages = _page_map(lines)
    headings = _parse_headings(lines, pages)
    course_headings = _course_section_headings(headings)
    boundaries = _course_boundaries(headings)

    courses = graph_data.get("courses", [])
    courses_by_code = {str(course["code"]): course for course in courses}
    course_names = {str(course["id"]): course["name"] for course in courses}
    course_lookup = graph_data.get("entity_resolution", {}).get("courses", {})
    if len(courses_by_code) != 126 or not isinstance(course_lookup, dict):
        raise HandbookProseError("Normalized course entities are incomplete")

    stream_records: list[dict[str, Any]] = []
    for number, name in STREAM_NAMES.items():
        section_number = f"2.2.{number}"
        heading = next(
            (item for item in headings if item.section_number == section_number), None
        )
        if heading is None:
            raise HandbookProseError(f"Missing stream section {section_number}")
        stream_records.append(
            {
                "id": f"subject-stream:{stable_slug(name)}",
                "name": name,
                "section_number": section_number,
                "source": {
                    "source_id": STRUCTURED_SOURCE_ID,
                    "path": source_path,
                    "markdown_line": heading.line_number,
                    "pdf_page": heading.pdf_page,
                },
            }
        )
    stream_by_number = {
        record["section_number"].split(".")[-1]: record
        for record in stream_records
    }

    extraction_units: list[dict[str, Any]] = []
    extraction_requests: list[dict[str, Any]] = []
    stream_links: set[tuple[str, str]] = set()
    prior_targets_by_stream: dict[str, list[str]] = {}
    for heading in course_headings:
        section_start = heading.line_number
        later_boundaries = [line for line in boundaries if line > section_start]
        section_end = (later_boundaries[0] - 1) if later_boundaries else len(lines)
        while section_end >= section_start and not lines[section_end - 1].strip():
            section_end -= 1
        stream_number = str(heading.section_number).split(".")[2]
        stream = stream_by_number[stream_number]
        prior_targets = prior_targets_by_stream.setdefault(stream_number, [])
        for unit in _extraction_unit_ranges(
            heading, section_start, section_end, lines
        ):
            start = int(unit["start"])
            end = int(unit["end"])
            while end >= start and not lines[end - 1].strip():
                end -= 1
            section_lines = lines[start - 1 : end]
            direct_target_ids = _resolve_section_targets(
                heading, section_lines, courses_by_code, course_lookup
            )
            evidence_text = "\n".join(section_lines).strip()
            shared_guidance = bool(SHARED_GUIDANCE_RE.search(evidence_text))
            target_ids = sorted(
                set(direct_target_ids)
                | (set(prior_targets) if shared_guidance else set())
            )
            for target_id in direct_target_ids:
                if target_id not in prior_targets:
                    prior_targets.append(target_id)
            for target_id in target_ids:
                stream_links.add((target_id, str(stream["id"])))

            page_values = [
                pages[line] for line in range(start, end + 1) if pages[line]
            ]
            if not page_values:
                raise HandbookProseError(
                    f"Section {heading.section_number} has no PDF page mapping"
                )
            evidence_lines = [
                {
                    "markdown_line": line_number,
                    "pdf_page": pages[line_number],
                    "text": lines[line_number - 1],
                }
                for line_number in range(start, end + 1)
            ]
            unit_key = unit["unit_key"]
            suffix = f":{unit_key}" if unit_key else ""
            section_id = f"course-section:{heading.section_number}{suffix}"
            eligibility_clauses = _eligibility_clauses(
                section_id,
                evidence_lines,
                academic_year=graph_data["dataset"].get("academic_year"),
            )
            section_record = {
                "id": section_id,
                "section_number": heading.section_number,
                "unit_key": unit_key,
                "title": unit["title"],
                "stream_id": stream["id"],
                "target_scope": (
                    "shared_with_preceding_sections"
                    if shared_guidance
                    else "direct"
                ),
                "direct_target_ids": direct_target_ids,
                "candidate_target_ids": target_ids,
                "eligibility_clause_count": len(eligibility_clauses),
                "source": {
                    "source_id": STRUCTURED_SOURCE_ID,
                    "path": source_path,
                    "markdown_line_start": start,
                    "markdown_line_end": end,
                    "pdf_page_start": min(page_values),
                    "pdf_page_end": max(page_values),
                },
            }
            extraction_units.append(section_record)
            request_suffix = f":{unit_key}" if unit_key else ""
            extraction_requests.append(
                {
                    "id": f"al-extraction:{heading.section_number}{request_suffix}",
                    "section_id": section_record["id"],
                    "section_number": heading.section_number,
                    "unit_key": unit_key,
                    "section_title": unit["title"],
                    "stream_id": stream["id"],
                    "target_scope": section_record["target_scope"],
                    "candidate_target_ids": target_ids,
                    "candidate_target_names": {
                        target_id: str(course_names.get(target_id, ""))
                        for target_id in target_ids
                    },
                    "reference_stream_subjects": _reference_stream_subjects(
                        evidence_lines
                    ),
                    "source": section_record["source"],
                    "evidence_text": evidence_text,
                    "evidence_lines": evidence_lines,
                    "eligibility_clauses": eligibility_clauses,
                }
            )

    covered_courses = sorted(
        {target for request in extraction_requests for target in request["candidate_target_ids"]}
    )
    unknown_targets = sorted(set(covered_courses) - {str(course["id"]) for course in courses})
    if unknown_targets:
        raise HandbookProseError(
            "Course sections contain unknown targets: " + ", ".join(unknown_targets)
        )

    structure = {
        "schema_version": SCHEMA_VERSION,
        "generation_stage": "deterministic_handbook_parsing",
        "dataset": graph_data["dataset"],
        "source": {
            "source_id": STRUCTURED_SOURCE_ID,
            "path": source_path,
            "checksum": source_checksum,
        },
        "validation_summary": {
            "status": "passed",
            "pdf_page_markers": len(page_markers),
            "headings": len(headings),
            "streams": len(stream_records),
            "course_sections": len(course_headings),
            "extraction_units": len(extraction_units),
            "covered_courses": len(covered_courses),
            "eligibility_clauses": sum(
                len(request["eligibility_clauses"])
                for request in extraction_requests
            ),
        },
        "page_markers": page_markers,
        "headings": [heading.to_dict() for heading in headings],
        "subject_streams": stream_records,
        "course_stream_links": [
            {"course_id": course_id, "stream_id": stream_id}
            for course_id, stream_id in sorted(stream_links)
        ],
        "course_sections": [
            {
                "id": f"course-section:{heading.section_number}",
                "section_number": heading.section_number,
                "title": heading.title,
                "markdown_line": heading.line_number,
            }
            for heading in course_headings
        ],
        "extraction_units": extraction_units,
    }
    requests = {
        "schema_version": SCHEMA_VERSION,
        "generation_stage": "al_extraction_request_preparation",
        "dataset": graph_data["dataset"],
        "source_checksum": source_checksum,
        "request_count": len(extraction_requests),
        "requests": extraction_requests,
    }
    return structure, requests


def extraction_schema(
    candidate_target_ids: Sequence[str],
    *,
    section_id: str | None = None,
    section_number: str | None = None,
    eligibility_clauses: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build the strict Structured Outputs schema for one bounded section."""

    if not candidate_target_ids:
        raise HandbookProseError("Extraction schema requires at least one target ID")
    string_array = {"type": "array", "items": {"type": "string"}}
    grade_counts = {
        "type": "object",
        "properties": {
            "required_a_grades": {"type": "integer"},
            "required_b_grades": {"type": "integer"},
            "required_c_grades": {"type": "integer"},
            "required_s_grades": {"type": "integer"},
            "grade_condition_text": {"type": "string"},
        },
        "required": [
            "required_a_grades",
            "required_b_grades",
            "required_c_grades",
            "required_s_grades",
            "grade_condition_text",
        ],
        "additionalProperties": False,
    }
    subject_group = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "subjects": string_array,
            "minimum_required": {"type": "integer"},
            "maximum_allowed": {"type": "integer"},
            "condition": {"type": "string"},
        },
        "required": [
            "name",
            "subjects",
            "minimum_required",
            "maximum_allowed",
            "condition",
        ],
        "additionalProperties": False,
    }
    subject_grade = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "minimum_grade": {"type": "string", "enum": ["A", "B", "C", "S"]},
            "alternatives": string_array,
            "condition": {"type": "string"},
        },
        "required": ["subject", "minimum_grade", "alternatives", "condition"],
        "additionalProperties": False,
    }
    common_general_paper = {
        "type": "object",
        "properties": {
            "required": {"type": "boolean"},
            "minimum_percentage": {"type": "integer"},
            "condition": {"type": "string"},
        },
        "required": ["required", "minimum_percentage", "condition"],
        "additionalProperties": False,
    }
    selection_constraint = {
        "type": "object",
        "properties": {
            "constraint_type": {
                "type": "string",
                "enum": [
                    "minimum_count",
                    "maximum_count",
                    "required_one_of",
                    "prohibited_combination",
                    "allowed_combination",
                    "only_from",
                    "exception",
                ],
            },
            "group_name": {"type": "string"},
            "subjects": string_array,
            "count": {"type": "integer"},
            "condition": {"type": "string"},
        },
        "required": [
            "constraint_type",
            "group_name",
            "subjects",
            "count",
            "condition",
        ],
        "additionalProperties": False,
    }
    source = {
        "type": "object",
        "properties": {
            "section": (
                {"type": "string", "enum": [section_number]}
                if section_number is not None
                else {"type": "string"}
            ),
            "pdf_page": {"type": "integer"},
            "markdown_line_start": {"type": "integer"},
            "markdown_line_end": {"type": "integer"},
        },
        "required": [
            "section",
            "pdf_page",
            "markdown_line_start",
            "markdown_line_end",
        ],
        "additionalProperties": False,
    }
    rule = {
        "type": "object",
        "properties": {
            "target_type": {"type": "string", "enum": ["Course"]},
            "target_id": {"type": "string", "enum": list(candidate_target_ids)},
            "requirement_type": {
                "type": "string",
                "enum": list(REQUIREMENT_TYPES),
            },
            "eligible_streams": string_array,
            "subjects": string_array,
            "subject_groups": {"type": "array", "items": subject_group},
            "minimum_grades": grade_counts,
            "subject_grade_requirements": {
                "type": "array",
                "items": subject_grade,
            },
            "common_general_paper": common_general_paper,
            "selection_constraints": {
                "type": "array",
                "items": selection_constraint,
            },
            "exception_to": {"type": "string"},
            "alternative_group": {"type": "string"},
            "alternative_option": {"type": "integer"},
            "conditions": string_array,
            "evidence_text": {"type": "string"},
            "source": source,
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "review_status": {"type": "string", "enum": ["proposed"]},
        },
        "required": [
            "target_type",
            "target_id",
            "requirement_type",
            "eligible_streams",
            "subjects",
            "subject_groups",
            "minimum_grades",
            "subject_grade_requirements",
            "common_general_paper",
            "selection_constraints",
            "exception_to",
            "alternative_group",
            "alternative_option",
            "conditions",
            "evidence_text",
            "source",
            "confidence",
            "review_status",
        ],
        "additionalProperties": False,
    }
    clause_ids = [str(item["id"]) for item in eligibility_clauses]
    clause_accounting = {
        "type": "object",
        "properties": {
            "clause_id": (
                {"type": "string", "enum": clause_ids}
                if clause_ids
                else {"type": "string"}
            ),
            "disposition": {
                "type": "string",
                "enum": list(CLAUSE_DISPOSITIONS),
            },
            "rule_numbers": {
                "type": "array",
                "items": {"type": "integer"},
            },
            "reason": {"type": "string", "enum": list(CLAUSE_IGNORE_REASONS)},
        },
        "required": ["clause_id", "disposition", "rule_numbers", "reason"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "section_id": (
                {"type": "string", "enum": [section_id]}
                if section_id is not None
                else {"type": "string"}
            ),
            "extraction_status": {
                "type": "string",
                "enum": ["rules_found", "no_rules", "needs_review"],
            },
            "rules": {"type": "array", "items": rule},
            "clause_accounting": {
                "type": "array",
                "items": clause_accounting,
            },
            "unresolved_text": string_array,
        },
        "required": [
            "section_id",
            "extraction_status",
            "rules",
            "clause_accounting",
            "unresolved_text",
        ],
        "additionalProperties": False,
    }


def _normalized_whitespace(value: str) -> str:
    return " ".join(value.split())


def _validate_clause_accounting(
    request: dict[str, Any],
    proposal: dict[str, Any],
    validated_rules: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    clauses = request.get("eligibility_clauses", [])
    expected = {str(item["id"]): item for item in clauses}
    accounting = proposal.get("clause_accounting")
    if not isinstance(accounting, list):
        raise HandbookProseError("Proposal clause_accounting must be a list")
    seen: dict[str, dict[str, Any]] = {}
    for item in accounting:
        if not isinstance(item, dict):
            raise HandbookProseError("Every clause accounting entry must be an object")
        clause_id = str(item.get("clause_id", ""))
        if clause_id not in expected:
            raise HandbookProseError(f"Unknown clause accounting ID: {clause_id!r}")
        if clause_id in seen:
            raise HandbookProseError(f"Clause was accounted more than once: {clause_id}")
        disposition = item.get("disposition")
        reason = item.get("reason")
        rule_numbers = item.get("rule_numbers")
        if disposition not in CLAUSE_DISPOSITIONS:
            raise HandbookProseError(f"Invalid clause disposition: {disposition!r}")
        if reason not in CLAUSE_IGNORE_REASONS:
            raise HandbookProseError(f"Invalid clause accounting reason: {reason!r}")
        if not isinstance(rule_numbers, list) or any(
            not isinstance(number, int) for number in rule_numbers
        ):
            raise HandbookProseError("Clause rule_numbers must be an integer array")
        if disposition == "extracted":
            scope_hint = str(expected[clause_id].get("scope_hint", ""))
            if scope_hint in EXPECTED_IGNORE_REASON:
                raise HandbookProseError(
                    f"Excluded clause {clause_id} cannot be marked extracted"
                )
            if reason != "not_ignored" or not rule_numbers:
                raise HandbookProseError(
                    "Extracted clauses require rule_numbers and reason=not_ignored"
                )
            clause = expected[clause_id]
            clause_start = int(clause["markdown_line_start"])
            clause_end = int(clause["markdown_line_end"])
            for number in rule_numbers:
                if number < 1 or number > len(validated_rules):
                    raise HandbookProseError(
                        f"Clause {clause_id} cites missing rule number {number}"
                    )
                source = validated_rules[number - 1]["source"]
                if not (
                    int(source["markdown_line_start"])
                    <= clause_start
                    <= clause_end
                    <= int(source["markdown_line_end"])
                ):
                    raise HandbookProseError(
                        f"Rule {number} does not cite the source line for {clause_id}"
                    )
        else:
            if rule_numbers:
                raise HandbookProseError(
                    "Ignored or unresolved clauses cannot cite rule_numbers"
                )
            if disposition == "intentionally_ignored" and reason == "not_ignored":
                raise HandbookProseError("Ignored clauses require an ignore reason")
            if disposition == "intentionally_ignored":
                scope_hint = str(expected[clause_id].get("scope_hint", ""))
                expected_reason = EXPECTED_IGNORE_REASON.get(scope_hint)
                if expected_reason is None:
                    raise HandbookProseError(
                        f"A/L candidate clause {clause_id} cannot be intentionally ignored"
                    )
                if reason != expected_reason:
                    raise HandbookProseError(
                        f"Clause {clause_id} has scope {scope_hint} and must use "
                        f"ignore reason {expected_reason}"
                    )
            if disposition == "needs_review" and reason != "not_ignored":
                raise HandbookProseError(
                    "Unresolved clauses must use reason=not_ignored"
                )
        seen[clause_id] = dict(item)
    missing = sorted(set(expected) - set(seen))
    if missing:
        raise HandbookProseError(
            "Eligibility clauses were not accounted for: " + ", ".join(missing)
        )
    return [seen[str(item["id"])] for item in clauses]


def _surface(text: str) -> str:
    """Comparable form of handbook text: bullets, '&' and line breaks removed."""

    value = re.sub(r"(?m)^\s*(?:[-*]|\d+\.)\s+", " ", text.replace("**", ""))
    value = re.sub(r"\s*-\s*", " ", value)
    value = value.replace("&", " and ").replace("‘", "'").replace("’", "'")
    return " ".join(value.casefold().split())


SUBJECT_SURFACES: dict[str, list[str]] = {subject: [_surface(subject)] for subject in AL_SUBJECTS}
for _alias, _subject in SUBJECT_ALIASES.items():
    SUBJECT_SURFACES[_subject].append(_surface(_alias))


def _named_in(surface_text: str, forms: Sequence[str]) -> bool:
    return any(
        re.search(r"(?<![a-z])" + re.escape(form) + r"(?![a-z])", surface_text)
        for form in forms
    )


STREAM_SUBJECT_REFERENCE_RE = re.compile(
    r"\bsubjects? from (?:the )?(?P<streams>[A-Za-z ]+? Streams?"
    r"(?:\s*(?:,|or|and)\s*(?:the )?[A-Za-z ]+? Streams?)*)",
    re.IGNORECASE,
)


def _reference_stream_subjects(
    evidence_lines: Sequence[dict[str, Any]],
) -> dict[str, list[str]]:
    """Owner stream-subject lists for streams the unit counts subjects *from*.

    The handbook never lists the subjects of a stream; when a unit needs them
    ("Two subjects from the Biological Science Stream or Physical Science
    Stream"), the request carries the owner's lists, labelled as such.
    """

    owner = OWNER_INTERPRETATIONS
    if not owner.is_file():
        return {}
    lists = json.loads(owner.read_text(encoding="utf-8")).get("stream_subjects", {})
    known = lists.get("streams", {})
    found: dict[str, list[str]] = {}
    for line in evidence_lines:
        for match in STREAM_SUBJECT_REFERENCE_RE.finditer(str(line["text"])):
            for name in re.split(r"\s+or\s+|\s*,\s*|\s+and\s+", match.group("streams")):
                stream = canonical_stream(re.sub(r"\s+Streams?$", "", name.strip(), flags=re.I))
                if stream in known:
                    found[stream] = list(known[stream])
    return found


def _al_text(request: dict[str, Any]) -> str:
    """The unit's evidence minus lines of excluded (O/L, aptitude, ...) clauses.

    Descriptive lines stay: they are not requirements of another kind (e.g.
    "subjects in the Arts Stream ... are classified under four baskets").
    """

    excluded: set[int] = set()
    for clause in request.get("eligibility_clauses", []):
        scope = str(clause.get("scope_hint", ""))
        if scope.startswith("excluded_") and scope != "excluded_descriptive":
            excluded.update(
                range(int(clause["markdown_line_start"]), int(clause["markdown_line_end"]) + 1)
            )
    # Headings name courses ("Applied Sciences (Physical Science)"); they do
    # not state requirements, so they never ground a subject or stream.
    return "\n".join(
        str(item["text"])
        for item in request["evidence_lines"]
        if int(item["markdown_line"]) not in excluded
        and not str(item["text"]).lstrip().startswith("#")
    )


def _check_rule_meaning(
    rule: dict[str, Any],
    al_text: str | None,
    reference_subjects: dict[str, list[str]] | None = None,
) -> None:
    """Normalise subject/stream names in place and ground them in A/L text.

    Quotes prove the text exists; these checks prove the rule's subjects and
    streams come from it: every name must be an A/L subject or stream, and
    each must be named in the unit's A/L text (excluded clauses removed), so
    nothing is inferred from headings, memory or O/L requirements.
    """

    def subjects_of(values: Any, field: str) -> list[str]:
        try:
            return normalize_subject_list(values if isinstance(values, list) else [])
        except NotEvaluable as exc:
            raise HandbookProseError(
                f"Rule {field} has a name that is not an A/L subject ({exc}); "
                "write each subject in full, exactly as the A/L subject is named"
            ) from exc

    rule["subjects"] = subjects_of(rule.get("subjects"), "subjects")
    groups = []
    for group in rule.get("subject_groups") or []:
        names = subjects_of(group.get("subjects"), "subject_groups")
        if not names and al_text is not None:
            raise HandbookProseError(
                "A subject_group must list its subjects; for 'subjects in the X Stream' "
                "use eligible_streams, and for an Arts reference use the Section 2.2.1.1 "
                "allowed_combination constraint"
            )
        groups.append({**group, "subjects": names})
    rule["subject_groups"] = groups
    items = []
    for item in rule.get("subject_grade_requirements") or []:
        options = subjects_of(
            [item.get("subject", ""), *(item.get("alternatives") or [])],
            "subject_grade_requirements",
        )
        if not options:
            raise HandbookProseError(
                "A subject_grade_requirements item must name at least one A/L subject"
            )
        items.append({**item, "subject": options[0], "alternatives": options[1:]})
    rule["subject_grade_requirements"] = items
    constraints = []
    for constraint in rule.get("selection_constraints") or []:
        names = subjects_of(constraint.get("subjects"), "selection_constraints")
        # Parser output may reference an Arts basket by name with no list.
        if not names and al_text is not None and constraint.get("constraint_type") in {
            "required_one_of", "prohibited_combination", "only_from", "maximum_count"
        }:
            raise HandbookProseError(
                f"A {constraint.get('constraint_type')} constraint must list its subjects"
            )
        constraints.append({**constraint, "subjects": names})
    rule["selection_constraints"] = constraints
    streams = []
    for value in rule.get("eligible_streams") or []:
        stream = canonical_stream(str(value))
        if stream is None:
            raise HandbookProseError(f"Rule eligible_streams has an unknown stream {value!r}")
        streams.append(stream)
    rule["eligible_streams"] = streams

    if al_text is None:
        return
    surface = _surface(al_text)
    reference = {s for subjects in (reference_subjects or {}).values() for s in subjects}
    named = set(rule["subjects"])
    for group in groups:
        named.update(group["subjects"])
    for item in items:
        named.update([item["subject"], *item["alternatives"]])
    for constraint in constraints:
        named.update(constraint["subjects"])
    missing = sorted(
        s for s in named
        if s not in reference and not _named_in(surface, SUBJECT_SURFACES[s])
    )
    if missing:
        raise HandbookProseError(
            "Rule names subjects that the excerpt's A/L text does not mention: "
            + ", ".join(missing)
        )
    for stream in streams:
        forms = [_surface(stream)] + [
            _surface(alias) for alias, value in STREAM_ALIASES.items() if value == stream
        ]
        if not _named_in(surface, forms):
            raise HandbookProseError(
                f"Rule requires the {stream} stream but the excerpt's A/L text does "
                "not state that stream; do not infer streams from headings"
            )


def validate_proposal(
    request: dict[str, Any],
    proposal: dict[str, Any],
    *,
    ground_names: bool = True,
) -> list[dict[str, Any]]:
    """Ground a model proposal locally and assign deterministic proposal IDs.

    ``ground_names=False`` is for deterministic parser output only: parsers
    may take a stream from the parent section ("2.2.1 ARTS STREAM") by design
    and are covered by their own anchor tests. Model output is always grounded.
    """

    if proposal.get("section_id") != request["section_id"]:
        raise HandbookProseError("Proposal section_id does not match its request")
    status = proposal.get("extraction_status")
    rules = proposal.get("rules")
    if status not in {"rules_found", "no_rules", "needs_review"}:
        raise HandbookProseError(f"Invalid extraction status: {status!r}")
    if not isinstance(rules, list):
        raise HandbookProseError("Proposal rules must be a list")
    if status == "no_rules" and rules:
        raise HandbookProseError("A no_rules proposal must have an empty rules list")
    if status == "rules_found" and not rules:
        raise HandbookProseError("A rules_found proposal must contain rules")
    unresolved_text = proposal.get("unresolved_text")
    if not isinstance(unresolved_text, list) or any(
        not isinstance(item, str) for item in unresolved_text
    ):
        raise HandbookProseError("Proposal unresolved_text must be a string array")
    if status == "needs_review" and not unresolved_text:
        raise HandbookProseError("A needs_review proposal requires unresolved_text")
    if status != "needs_review" and unresolved_text:
        raise HandbookProseError(
            "Only needs_review proposals may contain unresolved_text"
        )

    allowed_targets = set(request["candidate_target_ids"])
    evidence = _normalized_whitespace(request["evidence_text"])
    line_lookup = {
        int(item["markdown_line"]): str(item["text"])
        for item in request["evidence_lines"]
    }
    source_range = request["source"]
    al_text = _al_text(request) if ground_names else None
    validated: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(rules, start=1):
        if not isinstance(raw_rule, dict):
            raise HandbookProseError("Every proposed rule must be an object")
        rule = dict(raw_rule)
        target_id = rule.get("target_id")
        if target_id not in allowed_targets:
            raise HandbookProseError(f"Rule uses disallowed target {target_id!r}")
        if rule.get("target_type") != "Course":
            raise HandbookProseError("Rule target_type must be Course")
        if rule.get("requirement_type") not in REQUIREMENT_TYPES:
            raise HandbookProseError("Rule has an invalid requirement_type")
        if rule.get("review_status") != "proposed":
            raise HandbookProseError("Model rules must remain proposed")
        quote = str(rule.get("evidence_text", "")).strip()
        if not quote or _normalized_whitespace(quote) not in evidence:
            raise HandbookProseError("Rule evidence_text is not verbatim handbook evidence")
        if OL_EVIDENCE_RE.search(quote):
            raise HandbookProseError(
                "A/L extraction proposal contains an Ordinary Level requirement"
            )
        source = rule.get("source")
        if not isinstance(source, dict) or source.get("section") != request["section_number"]:
            raise HandbookProseError("Rule cites the wrong handbook section")
        start = int(source.get("markdown_line_start", 0))
        end = int(source.get("markdown_line_end", 0))
        page = int(source.get("pdf_page", 0))
        if not (
            source_range["markdown_line_start"]
            <= start
            <= end
            <= source_range["markdown_line_end"]
        ):
            raise HandbookProseError("Rule cites lines outside its bounded section")
        if not source_range["pdf_page_start"] <= page <= source_range["pdf_page_end"]:
            raise HandbookProseError("Rule cites a page outside its bounded section")
        cited_text = _normalized_whitespace(
            "\n".join(line_lookup.get(line, "") for line in range(start, end + 1))
        )
        if _normalized_whitespace(quote) not in cited_text:
            raise HandbookProseError("Evidence quote is not present in cited lines")
        _check_rule_meaning(rule, al_text, request.get("reference_stream_subjects"))
        group = rule.get("alternative_group", "")
        option = rule.get("alternative_option", 0)
        if not isinstance(group, str) or not isinstance(option, int):
            raise HandbookProseError("alternative_group/alternative_option have wrong types")
        if bool(group) != (option >= 1) or option < 0:
            raise HandbookProseError(
                "alternative_option must be >= 1 inside an alternative_group and 0 outside"
            )
        rule["alternative_group"] = group
        rule["alternative_option"] = option
        rule["id"] = (
            f"proposal:{request['section_number']}:"
            f"{target_id.removeprefix('course:')}:{index}"
        )
        rule["validation_status"] = "passed"
        validated.append(rule)
    options_by_group: dict[tuple[str, str], set[int]] = {}
    for rule in validated:
        if rule["alternative_group"]:
            options_by_group.setdefault(
                (str(rule["target_id"]), rule["alternative_group"]), set()
            ).add(rule["alternative_option"])
    for (target_id, group), options in options_by_group.items():
        if len(options) < 2:
            raise HandbookProseError(
                f"Alternative group {group!r} for {target_id} needs at least two options"
            )
    if status == "rules_found":
        covered_targets = {str(rule["target_id"]) for rule in validated}
        missing_targets = sorted(allowed_targets - covered_targets)
        if missing_targets:
            raise HandbookProseError(
                "Rules found but candidate targets were omitted: "
                + ", ".join(missing_targets)
            )
    accounting = _validate_clause_accounting(request, proposal, validated)
    advanced_clauses = {
        str(item["id"])
        for item in request.get("eligibility_clauses", [])
        if item.get("scope_hint") == "advanced_level_candidate"
    }
    dispositions = {
        str(item["clause_id"]): str(item["disposition"])
        for item in accounting
    }
    unresolved_clauses = {
        clause_id
        for clause_id, disposition in dispositions.items()
        if disposition == "needs_review"
    }
    if status == "no_rules" and advanced_clauses:
        raise HandbookProseError(
            "no_rules is not allowed when A/L eligibility clauses were detected"
        )
    if status == "rules_found":
        incomplete = sorted(
            clause_id
            for clause_id in advanced_clauses
            if dispositions.get(clause_id) != "extracted"
        )
        if incomplete:
            raise HandbookProseError(
                "rules_found did not extract every A/L eligibility clause: "
                + ", ".join(incomplete)
            )
    if status == "needs_review" and not unresolved_clauses:
        raise HandbookProseError(
            "needs_review requires at least one unresolved clause disposition"
        )
    if status != "needs_review" and unresolved_clauses:
        raise HandbookProseError(
            "Unresolved clauses require extraction_status=needs_review"
        )
    return validated


DEVELOPER_PROMPT = rule_extraction_prompt(AL_SUBJECTS, EXPECTED_IGNORE_REASON)


class OpenAIHandbookExtractionClient:
    """Minimal Responses API client for strict handbook-rule proposals."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 180,
        max_output_tokens: int = 8_000,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("HANDBOOK_EXTRACTION_MODEL") or os.getenv(
            "OPENAI_MODEL"
        )
        if not self.api_key:
            raise HandbookProseError("Set OPENAI_API_KEY before using --propose")
        if not self.model:
            raise HandbookProseError(
                "Set HANDBOOK_EXTRACTION_MODEL or OPENAI_MODEL before using --propose"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens

    def extract(
        self,
        request: dict[str, Any],
        schema: dict[str, Any],
        *,
        correction_history: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        input_messages: list[dict[str, Any]] = [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(request, ensure_ascii=False),
                    }
                ],
            },
        ]
        for attempt in correction_history:
            input_messages.extend(
                [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    attempt["raw_proposal"], ensure_ascii=False
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Your previous JSON failed deterministic local "
                                    f"validation: {attempt['validation_error']}\n"
                                    "Return the complete corrected JSON object. Preserve "
                                    "only claims grounded in the original excerpt. Do not "
                                    "invent evidence to satisfy validation; use a consistent "
                                    "needs_review abstention when grounding is insufficient."
                                ),
                            }
                        ],
                    },
                ]
            )
        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": self.max_output_tokens,
            "input": input_messages,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ugc_al_requirement_proposal",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        http_request = urllib.request.Request(
            self.base_url + "/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CampusYamu-HandbookExtractor/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                http_request, timeout=self.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HandbookProseError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise HandbookProseError(f"OpenAI request failed: {exc.reason}") from exc
        return _structured_response(body)


def _structured_response(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") != "completed":
        detail = response.get("incomplete_details") or response.get("error")
        raise HandbookProseError(f"OpenAI response did not complete: {detail}")
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise HandbookProseError(
                    f"OpenAI refused extraction: {content.get('refusal')}"
                )
            if content.get("type") == "output_text":
                try:
                    value = json.loads(str(content.get("text", "")))
                except json.JSONDecodeError as exc:
                    raise HandbookProseError(
                        "OpenAI returned invalid structured JSON"
                    ) from exc
                if not isinstance(value, dict):
                    raise HandbookProseError("OpenAI returned a non-object proposal")
                return value
    raise HandbookProseError("OpenAI response contained no structured output")


def _focused_retry_request(
    request: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any] | None:
    """Build a safe retry only when unresolved text covers every A/L clause."""

    if proposal.get("rules") or not proposal.get("unresolved_text"):
        return None
    advanced_clauses = [
        clause
        for clause in request.get("eligibility_clauses", [])
        if clause.get("scope_hint") == "advanced_level_candidate"
    ]
    if not advanced_clauses:
        return None
    unresolved = _normalized_whitespace(
        "\n".join(str(item) for item in proposal["unresolved_text"])
    )
    covered_clauses = [
        clause
        for clause in advanced_clauses
        if _normalized_whitespace(str(clause["text"])) in unresolved
    ]
    if {item["id"] for item in covered_clauses} != {
        item["id"] for item in advanced_clauses
    }:
        return None

    matching_lines = [
        int(item["markdown_line"])
        for item in request["evidence_lines"]
        if str(item["text"]).strip()
        and _normalized_whitespace(str(item["text"])) in unresolved
    ]
    if not matching_lines:
        return None
    start, end = min(matching_lines), max(matching_lines)
    evidence_lines = [
        item
        for item in request["evidence_lines"]
        if start <= int(item["markdown_line"]) <= end
    ]
    page_values = [int(item["pdf_page"]) for item in evidence_lines if item["pdf_page"]]
    if not page_values:
        return None
    retry = dict(request)
    retry["id"] = f"{request['id']}:retry-1"
    retry["retry_of"] = request["id"]
    retry["evidence_lines"] = evidence_lines
    retry["evidence_text"] = "\n".join(
        str(item["text"]) for item in evidence_lines
    ).strip()
    retry["eligibility_clauses"] = covered_clauses
    retry["source"] = {
        **request["source"],
        "markdown_line_start": start,
        "markdown_line_end": end,
        "pdf_page_start": min(page_values),
        "pdf_page_end": max(page_values),
    }
    return retry


def _merge_successful_retry(
    request: dict[str, Any],
    initial: dict[str, Any],
    retry: dict[str, Any],
) -> dict[str, Any]:
    retry_accounting = {
        str(item["clause_id"]): item for item in retry["clause_accounting"]
    }
    initial_accounting = {
        str(item["clause_id"]): item for item in initial["clause_accounting"]
    }
    return {
        "section_id": request["section_id"],
        "extraction_status": "rules_found",
        "rules": retry["rules"],
        "clause_accounting": [
            retry_accounting.get(str(clause["id"]))
            or initial_accounting[str(clause["id"])]
            for clause in request.get("eligibility_clauses", [])
        ],
        "unresolved_text": [],
    }


def _selection_constraint(
    constraint_type: str,
    group_name: str,
    count: int,
    condition: str,
    subjects: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "constraint_type": constraint_type,
        "group_name": group_name,
        "subjects": list(subjects),
        "count": count,
        "condition": condition,
    }


def _deterministic_arts_specs(
    unit_key: str,
    clauses: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    texts = [str(clause["text"]) for clause in clauses]

    def constraint(
        index: int,
        constraint_type: str,
        group_name: str,
        count: int,
        subjects: Sequence[str] = (),
    ) -> dict[str, Any]:
        return _selection_constraint(
            constraint_type,
            group_name,
            count,
            texts[index],
            subjects,
        )

    if unit_key == "general-core":
        expected = 2
        specs = [
            {
                "requirement_type": "al_minimum_grades",
                "required_s_grades": 3,
                "selection_constraints": [],
                "exception_to": "",
            },
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(1, "minimum_count", "Arts subject baskets", 3)
                ],
                "exception_to": "",
            },
        ]
    elif unit_key == "basket-1":
        expected = 6
        specs = [
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(0, "minimum_count", "Basket 01", 1)
                ],
                "exception_to": "",
            },
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(1, "allowed_combination", "Basket 01", 3)
                ],
                "exception_to": "",
            },
            {
                "requirement_type": "al_exception",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(
                        2,
                        "allowed_combination",
                        "National Languages",
                        3,
                        ("Sinhala", "Tamil", "English"),
                    )
                ],
                "exception_to": "Basket 01 minimum subject requirement",
            },
            {
                "requirement_type": "al_exception",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(
                        3,
                        "allowed_combination",
                        "National and Classical Languages",
                        0,
                    )
                ],
                "exception_to": "Basket 01 minimum subject requirement",
            },
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(4, "maximum_count", "Classical Languages", 2),
                    constraint(
                        4, "prohibited_combination", "Classical Languages", 3
                    ),
                ],
                "exception_to": "",
            },
            {
                "requirement_type": "al_exception",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(
                        5,
                        "allowed_combination",
                        "Two Languages plus Basket 02 or Basket 03",
                        3,
                    )
                ],
                "exception_to": "Basket 01 minimum subject requirement",
            },
        ]
    elif unit_key == "basket-2":
        expected = 2
        specs = [
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(0, "maximum_count", "Basket 02", 2)
                ],
                "exception_to": "",
            },
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(
                        1,
                        "prohibited_combination",
                        "Related religion and civilization",
                        2,
                    )
                ],
                "exception_to": "",
            },
        ]
    elif unit_key == "basket-3":
        expected = 1
        specs = [
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(0, "maximum_count", "Basket 03 subject areas", 2),
                    constraint(
                        0,
                        "prohibited_combination",
                        "Same Basket 03 subject area",
                        2,
                    ),
                ],
                "exception_to": "",
            }
        ]
    elif unit_key == "basket-4":
        expected = 1
        specs = [
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(0, "maximum_count", "Basket 04", 2)
                ],
                "exception_to": "",
            }
        ]
    elif unit_key == "cross-basket-exceptions":
        expected = 3
        specs = [
            {
                "requirement_type": "al_exception",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(0, "allowed_combination", "National Languages", 3)
                ],
                "exception_to": "Basket 04 maximum subject requirement",
            },
            {
                "requirement_type": "al_exception",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(1, "minimum_count", "National Languages", 1),
                    constraint(1, "minimum_count", "Classical Languages", 2),
                ],
                "exception_to": "Basket 04 maximum subject requirement",
            },
            {
                "requirement_type": "al_basket_rule",
                "required_s_grades": 0,
                "selection_constraints": [
                    constraint(
                        2, "prohibited_combination", "Classical Languages", 3
                    ),
                    constraint(
                        2, "prohibited_combination", "Foreign Languages", 3
                    ),
                ],
                "exception_to": "",
            },
        ]
    else:
        raise HandbookProseError(f"Unsupported deterministic Arts unit: {unit_key}")
    if len(clauses) != expected:
        raise HandbookProseError(
            f"Deterministic Arts unit {unit_key} expected {expected} clauses, "
            f"found {len(clauses)}"
        )
    for index, anchor in enumerate(DETERMINISTIC_ARTS_ANCHORS[unit_key]):
        if anchor.casefold() not in _normalized_whitespace(texts[index]).casefold():
            raise HandbookProseError(
                f"Deterministic Arts unit {unit_key} clause {index + 1} no longer "
                f"matches its expected text ({anchor!r}); update the spec"
            )
    return specs


def deterministic_arts_proposal(
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Convert the stable, structured Arts basket units without an LLM."""

    unit_key = request.get("unit_key")
    if request.get("section_number") != "2.2.1.1" or unit_key not in DETERMINISTIC_ARTS_UNITS:
        return None
    clauses = request.get("eligibility_clauses", [])
    specs = _deterministic_arts_specs(str(unit_key), clauses)
    rules: list[dict[str, Any]] = []
    for clause, spec in zip(clauses, specs, strict=True):
        rules.append(
            {
                "target_type": "Course",
                "target_id": "course:019",
                "requirement_type": spec["requirement_type"],
                "eligible_streams": ["Arts"],
                "subjects": [],
                "subject_groups": [],
                "minimum_grades": {
                    "required_a_grades": 0,
                    "required_b_grades": 0,
                    "required_c_grades": 0,
                    "required_s_grades": spec["required_s_grades"],
                    "grade_condition_text": (
                        str(clause["text"])
                        if spec["required_s_grades"]
                        else ""
                    ),
                },
                "subject_grade_requirements": [],
                "common_general_paper": {
                    "required": False,
                    "minimum_percentage": 0,
                    "condition": "",
                },
                "selection_constraints": spec["selection_constraints"],
                "exception_to": spec["exception_to"],
                "conditions": [str(clause["text"])],
                "evidence_text": request["evidence_text"],
                "source": {
                    "section": request["section_number"],
                    "pdf_page": int(clause["pdf_page"]),
                    "markdown_line_start": request["source"]["markdown_line_start"],
                    "markdown_line_end": request["source"]["markdown_line_end"],
                },
                "confidence": "high",
                "review_status": "proposed",
            }
        )
    return {
        "section_id": request["section_id"],
        "extraction_status": "rules_found",
        "rules": rules,
        "clause_accounting": [
            {
                "clause_id": clause["id"],
                "disposition": "extracted",
                "rule_numbers": [index],
                "reason": "not_ignored",
            }
            for index, clause in enumerate(clauses, start=1)
        ],
        "unresolved_text": [],
    }


def _known_stream_name(value: str) -> str | None:
    wanted = _normalized_whitespace(value).casefold()
    for name in STREAM_NAMES.values():
        if name.casefold() == wanted:
            return name
    return None


def _following_bullet_lines(
    request: dict[str, Any],
    clause: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the bullet list that directly follows a clause, skipping blank lines."""

    clause_end = int(clause["markdown_line_end"])
    bullets: list[dict[str, Any]] = []
    for item in request["evidence_lines"]:
        if int(item["markdown_line"]) <= clause_end:
            continue
        text = str(item["text"]).strip()
        if not text:
            continue
        if not BULLET_ITEM_RE.match(text):
            break
        bullets.append(item)
    return bullets


def _subject_combination_specs(
    request: dict[str, Any],
    advanced: Sequence[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """Parse '<N> subjects from <Stream> Stream, subject to: Not more than ...'.

    Returns None unless every A/L clause matches a supported pattern, so a
    partially understood block is never converted deterministically.
    """

    header = SUBJECT_COMBINATION_HEADER_RE.match(str(advanced[0]["text"]).strip())
    if header is None or len(advanced) < 2:
        return None
    stream = _known_stream_name(header.group(2))
    if stream is None:
        return None
    specs: list[dict[str, Any]] = [
        {
            "clause": advanced[0],
            "lines": [],
            "requirement_type": "al_subject_combination",
            "stream": stream,
            "constraint": _selection_constraint(
                "minimum_count",
                f"{stream} Stream subjects",
                COUNT_WORDS[header.group(1).casefold()],
                str(advanced[0]["text"]).strip(),
            ),
        }
    ]
    for clause in advanced[1:]:
        text = str(clause["text"]).strip()
        match = MAXIMUM_COUNT_CLAUSE_RE.match(text)
        if match is None:
            return None
        remainder = match.group(2).strip()
        subjects: list[str] = []
        lines: list[dict[str, Any]] = []
        if FOLLOWING_SUBJECTS_RE.match(remainder):
            lines = _following_bullet_lines(request, clause)
            if not lines:
                return None
            subjects = [
                BULLET_ITEM_RE.match(str(item["text"]).strip()).group(1)  # type: ignore[union-attr]
                for item in lines
            ]
            group_name = "Listed subjects"
        else:
            group_name = SUBJECT_GROUP_PREFIX_RE.sub("", remainder)
        specs.append(
            {
                "clause": clause,
                "lines": lines,
                "requirement_type": "al_basket_rule",
                "stream": stream,
                "constraint": _selection_constraint(
                    "maximum_count",
                    group_name,
                    COUNT_WORDS[match.group(1).casefold()],
                    text,
                    subjects,
                ),
            }
        )
    return specs


def deterministic_subject_combination_proposal(
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Convert structured subject-combination blocks without an LLM.

    The block is accepted only when every A/L clause is understood; O/L,
    aptitude-test, and selection-process clauses are ignored with the reason
    their scope hint requires. Each rule quotes and cites only its own clause
    lines (plus any subject bullets), never the whole unit.
    """

    clauses = request.get("eligibility_clauses", [])
    advanced = [
        clause
        for clause in clauses
        if clause.get("scope_hint") == "advanced_level_candidate"
    ]
    if not advanced:
        return None
    if any(
        clause.get("scope_hint") != "advanced_level_candidate"
        and clause.get("scope_hint") not in EXPECTED_IGNORE_REASON
        for clause in clauses
    ):
        return None
    specs = _subject_combination_specs(request, advanced)
    if specs is None:
        return None

    rules: list[dict[str, Any]] = []
    rule_numbers: dict[str, list[int]] = {str(clause["id"]): [] for clause in advanced}
    for target_id in request["candidate_target_ids"]:
        for spec in specs:
            clause = spec["clause"]
            cited = [
                str(clause["text"]).strip(),
                *(str(item["text"]).strip() for item in spec["lines"]),
            ]
            line_end = (
                int(spec["lines"][-1]["markdown_line"])
                if spec["lines"]
                else int(clause["markdown_line_end"])
            )
            rules.append(
                {
                    "target_type": "Course",
                    "target_id": target_id,
                    "requirement_type": spec["requirement_type"],
                    "eligible_streams": [spec["stream"]],
                    "subjects": [],
                    "subject_groups": [],
                    "minimum_grades": {
                        "required_a_grades": 0,
                        "required_b_grades": 0,
                        "required_c_grades": 0,
                        "required_s_grades": 0,
                        "grade_condition_text": "",
                    },
                    "subject_grade_requirements": [],
                    "common_general_paper": {
                        "required": False,
                        "minimum_percentage": 0,
                        "condition": "",
                    },
                    "selection_constraints": [spec["constraint"]],
                    "exception_to": "",
                    "conditions": [str(clause["text"]).strip()],
                    "evidence_text": "\n".join(cited),
                    "source": {
                        "section": request["section_number"],
                        "pdf_page": int(clause["pdf_page"]),
                        "markdown_line_start": int(clause["markdown_line_start"]),
                        "markdown_line_end": line_end,
                    },
                    "confidence": "high",
                    "review_status": "proposed",
                }
            )
            rule_numbers[str(clause["id"])].append(len(rules))

    accounting: list[dict[str, Any]] = []
    for clause in clauses:
        clause_id = str(clause["id"])
        if clause_id in rule_numbers:
            accounting.append(
                {
                    "clause_id": clause_id,
                    "disposition": "extracted",
                    "rule_numbers": rule_numbers[clause_id],
                    "reason": "not_ignored",
                }
            )
        else:
            accounting.append(
                {
                    "clause_id": clause_id,
                    "disposition": "intentionally_ignored",
                    "rule_numbers": [],
                    "reason": EXPECTED_IGNORE_REASON[str(clause["scope_hint"])],
                }
            )
    return {
        "section_id": request["section_id"],
        "extraction_status": "rules_found",
        "rules": rules,
        "clause_accounting": accounting,
        "unresolved_text": [],
    }


def _next_content_line(
    request: dict[str, Any], after_line: int
) -> dict[str, Any] | None:
    for item in request["evidence_lines"]:
        if int(item["markdown_line"]) <= after_line:
            continue
        text = str(item["text"]).strip()
        if text and not text.startswith("<!--"):
            return item
    return None


def _clause_rule_fields(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in spec.items()
        if key not in {"consumed_following_lines", "parser"}
    }


def deterministic_clause_proposal(
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Convert a unit whose every A/L clause matches a known phrasing.

    Safety rules (any failure returns None so the LLM harness handles it):
    * every advanced_level_candidate clause must parse (all-or-nothing);
    * an "or" line or a "Category (X)" heading between A/L clauses starts a
      new alternative: the clauses become OR'd options of one
      alternative_group (clauses inside one option stay AND'd);
    * the line after each clause (or after its consumed subject list) must end
      the requirement: another ledger clause, an "and" joiner, an "or" that is
      followed by another A/L clause, metadata, a heading, or an O/L intro.
      Otherwise the unit has requirement text the clause ledger did not
      capture, and a partial rule would be wrong.
    """

    clauses = request.get("eligibility_clauses", [])
    advanced = [
        clause
        for clause in clauses
        if clause.get("scope_hint") == "advanced_level_candidate"
    ]
    if not advanced or any(
        clause.get("scope_hint") != "advanced_level_candidate"
        and clause.get("scope_hint") not in EXPECTED_IGNORE_REASON
        for clause in clauses
    ):
        return None
    first = int(advanced[0]["markdown_line_start"])
    last = int(advanced[-1]["markdown_line_end"])
    boundaries = [
        int(item["markdown_line"])
        for item in request["evidence_lines"]
        if first < int(item["markdown_line"]) < last
        and (
            OR_SEPARATOR_RE.match(str(item["text"]).strip())
            or CATEGORY_HEADING_RE.match(str(item["text"]).strip())
        )
    ]
    clause_starts = {int(clause["markdown_line_start"]) for clause in clauses}

    items: list[tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]] = []
    previous_subjects: list[str] = []
    options_seen: set[int] = set()
    for clause in advanced:
        bullets = _following_bullet_lines(request, clause)
        spec = parse_al_clause(
            str(clause["text"]),
            [str(item["text"]) for item in bullets],
            previous_subjects=previous_subjects,
        )
        if spec is None:
            return None
        consumed = bullets[: spec["consumed_following_lines"]]
        end_line = (
            int(consumed[-1]["markdown_line"])
            if consumed
            else int(clause["markdown_line_end"])
        )
        if not _requirement_ends_after(
            request, end_line, clause_starts, or_allowed_before=last
        ):
            return None
        fields = _clause_rule_fields(spec)
        if boundaries:
            option = 1 + sum(
                line < int(clause["markdown_line_start"]) for line in boundaries
            )
            options_seen.add(option)
            fields["alternative_group"] = "alternatives-1"
            fields["alternative_option"] = option
        previous_subjects = list(spec.get("subjects", []))
        items.append((clause, fields, consumed))
    if boundaries and len(options_seen) < 2:
        return None
    return _assemble_clause_proposal(request, items)


def _requirement_ends_after(
    request: dict[str, Any],
    end_line: int,
    clause_starts: set[int],
    *,
    or_allowed_before: int = 0,
) -> bool:
    """True when the text after ``end_line`` cannot continue the requirement.

    An "or" line counts as an end only when it lies before
    ``or_allowed_before`` (i.e. another A/L clause follows it as the next
    alternative); an "or" after the last A/L clause introduces an alternative
    the ledger did not capture.
    """

    following = _next_content_line(request, end_line)
    if (
        following is not None
        and OR_SEPARATOR_RE.match(str(following["text"]).strip())
        and int(following["markdown_line"]) < or_allowed_before
    ):
        return True
    # An intro line ("In addition..., the following requirements;") is
    # acceptable only when what it introduces is itself a ledger clause.
    while (
        following is not None
        and int(following["markdown_line"]) not in clause_starts
        and CLAUSE_INTRO_RE.search(str(following["text"]))
    ):
        following = _next_content_line(request, int(following["markdown_line"]))
        if following is None or int(following["markdown_line"]) not in clause_starts:
            return False
    if following is None:
        return True
    text = str(following["text"]).strip()
    return bool(
        int(following["markdown_line"]) in clause_starts
        or AND_SEPARATOR_RE.match(text)
        or REQUIREMENT_END_RE.search(text)
        or (OL_EVIDENCE_RE.search(text) and not AL_EVIDENCE_RE.search(text))
    )


COURSE_CHOICE_CREDIT_RE = re.compile(
    r"^In the three subjects at the G\.C\.E\. \(Advanced Level\) Examination, students must "
    r"obtain at least two Ordinary Passes \(S\) in any two subjects and at least a Credit "
    r"Pass \(C\) for the subject the student wishes to follow\. This requirement is "
    r"mandatory\.(?P<examples>.*)$",
    re.IGNORECASE,
)
COURSE_CHOICE_EXAMPLE_RE = re.compile(
    r"student wishing to follow (?:a course of study in )?(?P<course>[A-Za-z& ]+?) must "
    r"(?:have obtained|have) a Credit Pass \(C\) or more (?:in|for) (?P<subject>[A-Za-z& ]+?) "
    r"at the G\.C\.E\.",
    re.IGNORECASE,
)


def _course_key(value: str) -> str:
    words = re.findall(r"[a-z]+", value.casefold().replace("&", " and "))
    return " ".join(word[:-1] if word.endswith("s") and len(word) > 3 else word for word in words)


def deterministic_course_choice_proposal(
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """'...at least a Credit Pass (C) for the subject the student wishes to follow.'

    The credited subject depends on the target course. It is taken from the
    clause's own examples ("a student wishing to follow Visual Arts must have
    ... C ... for Art"; confidence high), or else from an A/L subject with the
    same name as the course (Dance, Drama & Theatre; confidence medium, said
    so in the rule). Any target that resolves neither way declines the unit.
    """

    clauses = request.get("eligibility_clauses", [])
    advanced = [
        clause
        for clause in clauses
        if clause.get("scope_hint") == "advanced_level_candidate"
    ]
    if len(advanced) != 1 or any(
        clause.get("scope_hint") != "advanced_level_candidate"
        and clause.get("scope_hint") not in EXPECTED_IGNORE_REASON
        for clause in clauses
    ):
        return None
    clause = advanced[0]
    text = normalize_clause(str(clause["text"]))
    match = COURSE_CHOICE_CREDIT_RE.match(text)
    if match is None:
        return None
    stated: dict[str, str] = {}
    for example in COURSE_CHOICE_EXAMPLE_RE.finditer(match.group("examples")):
        subject = canonical_subject(example.group("subject"))
        if subject is None:
            return None
        stated[_course_key(example.group("course"))] = subject
    clause_starts = {int(item["markdown_line_start"]) for item in clauses}
    if not _requirement_ends_after(request, int(clause["markdown_line_end"]), clause_starts):
        return None

    names = request.get("candidate_target_names", {})
    raw_text = str(clause["text"]).strip()
    rules: list[dict[str, Any]] = []
    for target_id in request["candidate_target_ids"]:
        course_name = str(names.get(target_id, ""))
        subject = stated.get(_course_key(course_name))
        confidence = "high"
        condition = raw_text
        if subject is None:
            subject = canonical_subject(course_name)
            confidence = "medium"
            condition = (
                f"{raw_text} [Credited subject for {course_name} matched to the "
                "A/L subject of the same name; the handbook does not state it.]"
            )
        if subject is None:
            return None
        rules.append(
            {
                "target_type": "Course",
                "target_id": target_id,
                "requirement_type": "al_subject_combination",
                "eligible_streams": [],
                "subjects": [subject],
                "subject_groups": [],
                "minimum_grades": {
                    "required_a_grades": 0,
                    "required_b_grades": 0,
                    "required_c_grades": 1,
                    "required_s_grades": 2,
                    "grade_condition_text": raw_text,
                },
                "subject_grade_requirements": [
                    {
                        "subject": subject,
                        "minimum_grade": "C",
                        "alternatives": [],
                        "condition": condition,
                    }
                ],
                "common_general_paper": {
                    "required": False,
                    "minimum_percentage": 0,
                    "condition": "",
                },
                "selection_constraints": [
                    {
                        "constraint_type": "minimum_count",
                        "group_name": "Any other subjects",
                        "subjects": [],
                        "count": 2,
                        "condition": raw_text,
                    }
                ],
                "exception_to": "",
                "conditions": [condition],
                "evidence_text": raw_text,
                "source": {
                    "section": request["section_number"],
                    "pdf_page": int(clause["pdf_page"]),
                    "markdown_line_start": int(clause["markdown_line_start"]),
                    "markdown_line_end": int(clause["markdown_line_end"]),
                },
                "confidence": confidence,
                "review_status": "proposed",
            }
        )
    return {
        "section_id": request["section_id"],
        "extraction_status": "rules_found",
        "rules": rules,
        "clause_accounting": [
            {
                "clause_id": str(item["id"]),
                "disposition": "extracted",
                "rule_numbers": list(range(1, len(rules) + 1)),
                "reason": "not_ignored",
            }
            if item is clause
            else {
                "clause_id": str(item["id"]),
                "disposition": "intentionally_ignored",
                "rule_numbers": [],
                "reason": EXPECTED_IGNORE_REASON[str(item["scope_hint"])],
            }
            for item in clauses
        ],
        "unresolved_text": [],
    }


def _assemble_clause_proposal(
    request: dict[str, Any],
    items: Sequence[tuple[dict[str, Any], dict[str, Any], Sequence[dict[str, Any]]]],
) -> dict[str, Any]:
    """Build one rule per (target, clause); each rule cites only its own lines."""

    rules: list[dict[str, Any]] = []
    rule_numbers: dict[str, list[int]] = {str(clause["id"]): [] for clause, _, _ in items}
    for target_id in request["candidate_target_ids"]:
        for clause, fields, extra_lines in items:
            cited = [
                str(clause["text"]).strip(),
                *(str(line["text"]).strip() for line in extra_lines),
            ]
            line_end = (
                int(extra_lines[-1]["markdown_line"])
                if extra_lines
                else int(clause["markdown_line_end"])
            )
            rules.append(
                {
                    "target_type": "Course",
                    "target_id": target_id,
                    **fields,
                    "exception_to": fields.get("exception_to", ""),
                    "conditions": [str(clause["text"]).strip()],
                    "evidence_text": "\n".join(cited),
                    "source": {
                        "section": request["section_number"],
                        "pdf_page": int(clause["pdf_page"]),
                        "markdown_line_start": int(clause["markdown_line_start"]),
                        "markdown_line_end": line_end,
                    },
                    "confidence": "high",
                    "review_status": "proposed",
                }
            )
            rule_numbers[str(clause["id"])].append(len(rules))

    accounting: list[dict[str, Any]] = []
    for clause in request.get("eligibility_clauses", []):
        clause_id = str(clause["id"])
        if clause_id in rule_numbers:
            accounting.append(
                {
                    "clause_id": clause_id,
                    "disposition": "extracted",
                    "rule_numbers": rule_numbers[clause_id],
                    "reason": "not_ignored",
                }
            )
        else:
            accounting.append(
                {
                    "clause_id": clause_id,
                    "disposition": "intentionally_ignored",
                    "rule_numbers": [],
                    "reason": EXPECTED_IGNORE_REASON[str(clause["scope_hint"])],
                }
            )
    return {
        "section_id": request["section_id"],
        "extraction_status": "rules_found",
        "rules": rules,
        "clause_accounting": accounting,
        "unresolved_text": [],
    }


def _is_header_only_line(text: str) -> bool:
    compact = re.sub(r"[*\s]", "", text).casefold()
    return (
        not compact
        or text.lstrip().startswith(("#", "<!--"))
        or compact.startswith(("(coursecode", "(proposedintake"))
    )


def deterministic_header_only_proposal(
    request: dict[str, Any],
) -> dict[str, Any] | None:
    """Return no_rules for units that contain only a heading, code and intake.

    Such units (e.g. 2.2.2.1-2.2.2.3) get their requirements from a later
    shared-guidance unit ("above mentioned courses"), which lists them as
    candidate targets. With an empty clause ledger there is nothing for a
    model to account for, and it tends to invent clause IDs instead.
    """

    if request.get("eligibility_clauses"):
        return None
    if not all(
        _is_header_only_line(str(item["text"])) for item in request["evidence_lines"]
    ):
        return None
    return {
        "section_id": request["section_id"],
        "extraction_status": "no_rules",
        "rules": [],
        "clause_accounting": [],
        "unresolved_text": [],
    }


def deterministic_proposal(request: dict[str, Any]) -> dict[str, Any] | None:
    """Try every deterministic parser before falling back to the LLM harness."""

    return (
        deterministic_header_only_proposal(request)
        or deterministic_arts_proposal(request)
        or deterministic_subject_combination_proposal(request)
        or deterministic_course_choice_proposal(request)
        or deterministic_clause_proposal(request)
    )


def _run_guarded_extraction(
    request: dict[str, Any],
    model: RuleExtractionModel,
    *,
    max_attempts: int,
    on_validation_retry: Callable[[int, str], None] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract, validate, and feed exact failures back for bounded correction."""

    schema = extraction_schema(
        request["candidate_target_ids"],
        section_id=request["section_id"],
        section_number=request["section_number"],
        eligibility_clauses=request.get("eligibility_clauses", []),
    )
    correction_history: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for attempt_number in range(1, max_attempts + 1):
        raw = model.extract(
            request,
            schema,
            correction_history=correction_history,
        )
        try:
            validated = validate_proposal(request, raw)
        except (KeyError, TypeError, ValueError, HandbookProseError) as exc:
            entry = {
                "attempt": attempt_number,
                "status": "rejected",
                "validation_error": str(exc),
                "raw_proposal": raw,
            }
            audit.append(entry)
            correction_history.append(entry)
            if attempt_number < max_attempts and on_validation_retry is not None:
                on_validation_retry(attempt_number + 1, str(exc))
            continue
        audit.append(
            {
                "attempt": attempt_number,
                "status": "accepted",
                "validation_error": None,
                "raw_proposal": raw,
            }
        )
        return raw, validated, audit
    last_error = str(audit[-1]["validation_error"])
    raise ExtractionHarnessError(
        f"Validation harness exhausted {max_attempts} attempts: {last_error}",
        audit,
    )


REVIEW_STATUSES = ("auto_accepted", "unverified", "unresolved")


class _DeterministicOnlyModel:
    """Placeholder model for runs where every selected unit is deterministic,
    so no API key is needed."""

    model = "deterministic-only"

    def extract(self, request, schema, *, correction_history=()):  # noqa: ANN001
        raise HandbookProseError("Deterministic-only run attempted a model call")


def _rule_signature(rules: Sequence[dict[str, Any]]) -> list[str]:
    """Order-insensitive semantic fingerprint of validated rules.

    Ignores wording (conditions, group names, evidence, line ranges) and
    compares only what an eligibility check would use.
    """

    mandatory: list[str] = []
    groups: dict[tuple[str, str], dict[int, list[str]]] = {}
    for rule in rules:
        single = _single_rule_signature(rule)
        group = str(rule.get("alternative_group", ""))
        if not group:
            mandatory.append(single)
            continue
        options = groups.setdefault((str(rule.get("target_id")), group), {})
        options.setdefault(int(rule.get("alternative_option", 0)), []).append(single)
    # Group names and option numbers are arbitrary labels: compare the
    # structure (a set of options, each a set of rules) instead.
    structured = [
        json.dumps(
            {"alternatives": sorted(json.dumps(sorted(option)) for option in options.values())},
            sort_keys=True,
        )
        for options in groups.values()
    ]
    return sorted(mandatory) + sorted(structured)


def _single_rule_signature(rule: dict[str, Any]) -> str:
    signature: list[str] = []
    for rule in (rule,):
        grades = rule.get("minimum_grades", {})
        cgp = rule.get("common_general_paper", {})
        signature.append(
            json.dumps(
                {
                    "target": rule.get("target_id"),
                    "type": rule.get("requirement_type"),
                    "streams": sorted(rule.get("eligible_streams", [])),
                    "subjects": sorted(rule.get("subjects", [])),
                    # Group names are labels; compare the lists and limits only.
                    "groups": sorted(
                        (
                            sorted(group.get("subjects", [])),
                            int(group.get("minimum_required", 0)),
                            int(group.get("maximum_allowed", 0)),
                        )
                        for group in rule.get("subject_groups", [])
                    ),
                    "grades": [
                        grades.get(f"required_{grade}_grades", 0)
                        for grade in ("a", "b", "c", "s")
                    ],
                    "subject_grades": sorted(
                        (
                            item.get("subject"),
                            item.get("minimum_grade"),
                            sorted(item.get("alternatives", [])),
                        )
                        for item in rule.get("subject_grade_requirements", [])
                    ),
                    "constraints": sorted(
                        (
                            item.get("constraint_type"),
                            int(item.get("count", 0)),
                            sorted(item.get("subjects", [])),
                        )
                        for item in rule.get("selection_constraints", [])
                    ),
                    "cgp": int(cgp.get("minimum_percentage", 0))
                    if cgp.get("required")
                    else 0,
                },
                sort_keys=True,
            )
        )
    return signature[0]


def _rules_agree(
    first: Sequence[dict[str, Any]], second: Sequence[dict[str, Any]]
) -> tuple[bool, str]:
    """Do two validated rule sets admit exactly the same students?

    Uses the executable semantics in ``al_rule_semantics`` so the same
    requirement written in different schema fields still agrees. Falls back to
    the structural fingerprint only when a rule cannot be executed (Arts basket
    references, non-A/L requirements, unknown subject names).
    """

    semantic = equivalent_rule_sets(first, second)
    if semantic is not None:
        return semantic, "semantic"
    return _rule_signature(first) == _rule_signature(second), "structural"


def _rereview(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Re-score a stored two-model result with the current comparison."""

    if result.get("review_basis") not in {"model_consensus", "model_disagreement"}:
        return result
    verification = result.get("verification") or {}
    try:
        verifier_rules = validate_proposal(request, verification["raw_proposal"])
    except (KeyError, TypeError, ValueError, HandbookProseError):
        return result
    agree, comparison = _rules_agree(result["rules"], verifier_rules)
    return {
        **result,
        "review_status": "auto_accepted" if agree else "unresolved",
        "review_basis": "model_consensus" if agree else "model_disagreement",
        "verification": {**verification, "comparison": comparison},
    }


def load_interpretations(path: Path = OWNER_INTERPRETATIONS) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["request_id"]: item for item in data.get("interpretations", [])}


def _apply_interpretation(
    request: dict[str, Any],
    result: dict[str, Any],
    interpretation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Settle a model disagreement with the owner's recorded reading.

    The reading is a set of example results with expected decisions. Only a
    model rule set that reproduces every case is accepted; nothing is edited
    by hand, and the decision is recorded on the result.
    """

    if interpretation is None:
        return result
    settles = {"model_disagreement", "verifier_only", "verifier_abstained", "single_model"}
    if result.get("review_status") != "auto_accepted" and result.get("review_basis") not in settles:
        return result
    verification = result.get("verification") or {}
    try:
        verifier_rules = validate_proposal(request, verification["raw_proposal"])
    except (KeyError, TypeError, ValueError, HandbookProseError):
        verifier_rules = None
    candidates = [("primary", result["rules"], None)]
    if verifier_rules:
        candidates.append(("verifier", verifier_rules, verification["raw_proposal"]))

    def case_student(case: dict[str, Any]) -> Student:
        grades = []
        for entry in case["subjects"]:
            name, _, grade = str(entry).partition(":")
            grades.append((name, grade or "S"))
        return Student(tuple(grades), case.get("stream"), 30)

    def reproduces(rules: Sequence[dict[str, Any]]) -> bool:
        try:
            return all(
                evaluate_rules(rules, case_student(case)) == bool(case["eligible"])
                for case in interpretation["cases"]
            )
        except (NotEvaluable, KeyError, TypeError, ValueError):
            return False

    previously_settled = result.get("review_basis") == "owner_interpretation"
    if previously_settled:
        # An earlier owner selection is kept only while it matches the current
        # reading; when the owner changes the reading, the candidates are re-chosen.
        if reproduces(result["rules"]):
            selected = (result.get("interpretation") or {}).get("selected", "primary")
            return {**result, "interpretation": {**interpretation, "applied": True, "selected": selected}}
    elif result.get("review_status") == "auto_accepted":
        # Model agreement never overrides the owner's recorded reading.
        if reproduces(result["rules"]):
            return result
        return {
            **result,
            "review_status": "unresolved",
            "review_basis": "contradicts_owner_interpretation",
            "interpretation": {**interpretation, "applied": False},
        }
    matching = [candidate for candidate in candidates if reproduces(candidate[1])]
    if not matching:
        if previously_settled:
            return {
                **result,
                "review_status": "unresolved",
                "review_basis": "contradicts_owner_interpretation",
                "interpretation": {**interpretation, "applied": False},
            }
        return {**result, "interpretation": {**interpretation, "applied": False}}
    source, rules, raw = matching[0]
    accepted = {
        **result,
        "rules": rules,
        "review_status": "auto_accepted",
        "review_basis": "owner_interpretation",
        "interpretation": {**interpretation, "applied": True, "selected": source},
    }
    if raw is not None:
        accepted.update(
            extraction_status=raw["extraction_status"],
            clause_accounting=raw["clause_accounting"],
            unresolved_text=raw["unresolved_text"],
        )
    return accepted


def _auto_review(
    request: dict[str, Any],
    raw: dict[str, Any],
    validated_rules: list[dict[str, Any]],
    extraction_method: str,
    verifier: RuleExtractionModel | None,
    *,
    max_attempts: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], int]:
    """Decide a result's review status without a human in the loop.

    Returns (raw, validated_rules, review, model_calls). The verifier never
    overrides a validated answer it disagrees with; disagreement is recorded
    as unresolved so nothing unsupported is silently accepted.
    """

    if extraction_method == "deterministic":
        return raw, validated_rules, {
            "review_status": "auto_accepted",
            "review_basis": "deterministic_parser",
        }, 0
    primary_found = raw["extraction_status"] == "rules_found"
    if verifier is None:
        return raw, validated_rules, {
            "review_status": "unverified" if primary_found else "unresolved",
            "review_basis": "single_model" if primary_found else "model_abstained",
        }, 0
    try:
        verifier_raw, verifier_rules, verifier_attempts = _run_guarded_extraction(
            request, verifier, max_attempts=max_attempts
        )
    except ExtractionHarnessError as exc:
        return raw, validated_rules, {
            "review_status": "unverified" if primary_found else "unresolved",
            "review_basis": "verifier_failed",
            "verification": {"model": verifier.model, "error": str(exc)},
        }, exc.model_calls
    calls = len(verifier_attempts)
    verification = {
        "model": verifier.model,
        "extraction_status": verifier_raw["extraction_status"],
        "attempt_count": calls,
        "raw_proposal": verifier_raw,
    }
    verifier_found = verifier_raw["extraction_status"] == "rules_found"
    if primary_found and verifier_found:
        agree, comparison = _rules_agree(validated_rules, verifier_rules)
        verification["comparison"] = comparison
        return raw, validated_rules, {
            "review_status": "auto_accepted" if agree else "unresolved",
            "review_basis": "model_consensus" if agree else "model_disagreement",
            "verification": verification,
        }, calls
    if verifier_found:
        # Primary abstained; keep the verifier's validated answer but flag it.
        return verifier_raw, verifier_rules, {
            "review_status": "unverified",
            "review_basis": "verifier_only",
            "verification": {**verification, "primary_raw_proposal": raw},
        }, calls
    return raw, validated_rules, {
        "review_status": "unverified" if primary_found else "unresolved",
        "review_basis": "verifier_abstained" if primary_found else "both_abstained",
        "verification": verification,
    }, calls


def build_review_queue(
    proposals: dict[str, Any],
    pending_requests: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Collect non-accepted results into a non-blocking queue.

    Downstream (the graph builder) should use only auto_accepted rules as
    facts. Unverified rules (one model only) proved unreliable in practice
    (dropped alternatives, wrong grade counts), so treat them like unresolved
    units: attach the raw clause text so answers can quote the handbook, and
    mark the course's A/L requirements as incomplete.
    """

    items = []
    for result in proposals.get("results", []):
        if result.get("review_status") == "auto_accepted":
            continue
        items.append(
            {
                "request_id": result["request_id"],
                "section_number": result["section_number"],
                "review_status": result.get("review_status"),
                "review_basis": result.get("review_basis"),
                "extraction_method": result.get("extraction_method"),
                "rule_count": len(result.get("rules", [])),
                "unresolved_text": result.get("unresolved_text", []),
            }
        )
    processed = {result["request_id"] for result in proposals.get("results", [])}
    pending = [
        {
            "request_id": request["id"],
            "section_number": request["section_number"],
            "review_status": "pending_llm",
            "advanced_level_clauses": [
                clause["text"]
                for clause in request.get("eligibility_clauses", [])
                if clause.get("scope_hint") == "advanced_level_candidate"
            ],
        }
        for request in pending_requests
        if request["id"] not in processed
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generation_stage": "al_rule_review_queue",
        "blocking": False,
        "item_count": len(items),
        "items": items,
        "pending_count": len(pending),
        "pending": pending,
    }


def refresh_deterministic(
    proposals: dict[str, Any],
    requests: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Merge an earlier proposals file with the current deterministic parsers.

    No model calls. Units that are now deterministic are regenerated; earlier
    LLM results are kept only for units that still need the LLM and still
    validate against the current clause ledger. Returns (proposals, report,
    dropped request IDs that need a fresh LLM run).
    """

    previous = {result["request_id"]: result for result in proposals.get("results", [])}
    interpretations = load_interpretations()
    deterministic = [item for item in requests if deterministic_proposal(item) is not None]
    fresh, _ = propose_rules(deterministic, _DeterministicOnlyModel())
    fresh_by_id = {result["request_id"]: result for result in fresh["results"]}
    results: list[dict[str, Any]] = []
    dropped: list[str] = []
    for request in requests:
        request_id = request["id"]
        if request_id in fresh_by_id:
            results.append(fresh_by_id[request_id])
            continue
        old = previous.get(request_id)
        if old is None:
            continue
        try:
            raw = {
                "section_id": old["section_id"],
                "extraction_status": old["extraction_status"],
                "rules": [
                    {k: v for k, v in rule.items() if k not in {"id", "validation_status"}}
                    for rule in old["rules"]
                ],
                "clause_accounting": old["clause_accounting"],
                "unresolved_text": old["unresolved_text"],
            }
            validate_proposal(request, raw)
            results.append(
                _apply_interpretation(
                    request, _rereview(request, old), interpretations.get(request_id)
                )
            )
        except (KeyError, TypeError, ValueError, HandbookProseError):
            dropped.append(request_id)
    needs_review = sum(result["semantic_status"] == "needs_review" for result in results)
    merged = {**proposals, "results": results, "review_status": "automated"}
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_review" if needs_review or dropped else "passed",
        "requests_attempted": len(results),
        "model_calls": 0,
        "requests_validated": len(results),
        "validated_rules": sum(len(result["rules"]) for result in results),
        "semantically_complete_requests": len(results) - needs_review,
        "requests_needing_review": needs_review,
        "review_counts": {
            status: sum(result.get("review_status") == status for result in results)
            for status in REVIEW_STATUSES
        },
        "dropped_stale_results": dropped,
        "failures": [],
        "database_write_attempted": False,
    }
    return merged, report, dropped


def open_requests(
    requests: Sequence[dict[str, Any]],
    proposals: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """LLM units without an auto_accepted result in an earlier proposals file."""

    accepted = {
        result["request_id"]
        for result in (proposals or {}).get("results", [])
        if result.get("review_status") == "auto_accepted"
    }
    return [
        request
        for request in requests
        if request["id"] not in accepted and deterministic_proposal(request) is None
    ]


def merge_proposals(
    previous: dict[str, Any] | None,
    fresh: dict[str, Any],
    requests: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Overlay a partial run onto an earlier proposals file (no model calls).

    Fresh results replace earlier ones for the same request; everything else is
    re-checked by ``refresh_deterministic`` so the merged file stays consistent
    with the current parsers and clause ledger.
    """

    fresh_ids = {result["request_id"] for result in fresh["results"]}
    kept = [
        result
        for result in (previous or {}).get("results", [])
        if result["request_id"] not in fresh_ids
    ]
    base = {**(previous or {}), **{k: v for k, v in fresh.items() if k != "results"}}
    base["results"] = kept + list(fresh["results"])
    return refresh_deterministic(base, requests)


def propose_rules(
    requests: Sequence[dict[str, Any]],
    model: RuleExtractionModel,
    *,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    retry_needs_review: bool = False,
    max_attempts: int = 4,
    verifier: RuleExtractionModel | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call the model and locally validate every returned proposal.

    Deterministic units are auto-accepted. LLM units are cross-checked by an
    optional independent ``verifier`` model (see ``_auto_review``).
    """

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    validated_rule_count = 0
    model_calls = 0
    total = len(requests)
    for position, request in enumerate(requests, start=1):
        raw: dict[str, Any] | None = None
        started_at = time.monotonic()
        deterministic_raw = deterministic_proposal(request)
        extraction_method = (
            "deterministic" if deterministic_raw is not None else "llm_harness"
        )
        if on_progress is not None:
            on_progress(
                {
                    "event": "section_started",
                    "position": position,
                    "total": total,
                    "request_id": request["id"],
                    "section_number": request["section_number"],
                    "section_title": request["section_title"],
                    "target_count": len(request["candidate_target_ids"]),
                    "model": model.model,
                    "extraction_method": extraction_method,
                }
            )
        try:
            def report_validation_retry(attempt: int, error: str) -> None:
                if on_progress is not None:
                    on_progress(
                        {
                            "event": "section_validation_retry",
                            "position": position,
                            "total": total,
                            "request_id": request["id"],
                            "section_number": request["section_number"],
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "error": error,
                        }
                    )

            if deterministic_raw is not None:
                raw = deterministic_raw
                validated_rules = validate_proposal(request, raw, ground_names=False)
                harness_attempts: list[dict[str, Any]] = []
            else:
                raw, validated_rules, harness_attempts = _run_guarded_extraction(
                    request,
                    model,
                    max_attempts=max_attempts,
                    on_validation_retry=report_validation_retry,
                )
                model_calls += len(harness_attempts)
            retry_status = (
                "not_applicable"
                if extraction_method == "deterministic"
                else "not_attempted"
            )
            retry_error: str | None = None
            retry_attempts: list[dict[str, Any]] = []
            if (
                extraction_method == "llm_harness"
                and retry_needs_review
                and raw["extraction_status"] == "needs_review"
            ):
                retry_request = _focused_retry_request(request, raw)
                if retry_request is not None:
                    retry_status = "attempted"
                    if on_progress is not None:
                        on_progress(
                            {
                                "event": "section_retry_started",
                                "position": position,
                                "total": total,
                                "request_id": request["id"],
                                "section_number": request["section_number"],
                                "model": model.model,
                            }
                        )
                    try:
                        retry_raw, _, retry_attempts = _run_guarded_extraction(
                            retry_request,
                            model,
                            max_attempts=max_attempts,
                            on_validation_retry=report_validation_retry,
                        )
                        model_calls += len(retry_attempts)
                        if retry_raw["extraction_status"] == "rules_found":
                            merged = _merge_successful_retry(
                                request, raw, retry_raw
                            )
                            validated_rules = validate_proposal(request, merged)
                            raw = merged
                            retry_status = "resolved"
                        else:
                            retry_status = "still_needs_review"
                        if on_progress is not None:
                            on_progress(
                                {
                                    "event": "section_retry_completed",
                                    "position": position,
                                    "total": total,
                                    "request_id": request["id"],
                                    "section_number": request["section_number"],
                                    "retry_status": retry_status,
                                }
                            )
                    except ExtractionHarnessError as exc:
                        model_calls += exc.model_calls
                        retry_attempts = exc.attempts
                        retry_status = "failed"
                        retry_error = str(exc)
                        if on_progress is not None:
                            on_progress(
                                {
                                    "event": "section_retry_failed",
                                    "position": position,
                                    "total": total,
                                    "request_id": request["id"],
                                    "section_number": request["section_number"],
                                    "error": retry_error,
                                }
                            )
                    except (KeyError, TypeError, ValueError, HandbookProseError) as exc:
                        retry_status = "failed"
                        retry_error = str(exc)
                        if on_progress is not None:
                            on_progress(
                                {
                                    "event": "section_retry_failed",
                                    "position": position,
                                    "total": total,
                                    "request_id": request["id"],
                                    "section_number": request["section_number"],
                                    "error": retry_error,
                                }
                            )
            raw, validated_rules, review, verifier_calls = _auto_review(
                request,
                raw,
                validated_rules,
                extraction_method,
                verifier,
                max_attempts=max_attempts,
            )
            model_calls += verifier_calls
            validated_rule_count += len(validated_rules)
            result = {
                "request_id": request["id"],
                "section_id": request["section_id"],
                "section_number": request["section_number"],
                "extraction_status": raw["extraction_status"],
                "rules": validated_rules,
                "clause_accounting": raw["clause_accounting"],
                "unresolved_text": raw["unresolved_text"],
                "semantic_status": (
                    "needs_review"
                    if raw["extraction_status"] == "needs_review"
                    else "complete"
                ),
                **review,
                "retry_status": retry_status,
                "extraction_method": extraction_method,
                "model": model.model if extraction_method == "llm_harness" else None,
                "verifier_model": (
                    verifier.model
                    if verifier is not None and extraction_method == "llm_harness"
                    else None
                ),
                "harness": {
                    "max_attempts": max_attempts,
                    "attempt_count": len(harness_attempts),
                    "attempts": harness_attempts,
                },
            }
            if retry_attempts:
                result["retry_harness"] = {
                    "max_attempts": max_attempts,
                    "attempt_count": len(retry_attempts),
                    "attempts": retry_attempts,
                }
            if retry_error is not None:
                result["retry_error"] = retry_error
            results.append(result)
            if on_progress is not None:
                on_progress(
                    {
                        "event": "section_completed",
                        "position": position,
                        "total": total,
                        "request_id": request["id"],
                        "section_number": request["section_number"],
                        "rule_count": len(validated_rules),
                        "extraction_status": raw["extraction_status"],
                        "elapsed_seconds": time.monotonic() - started_at,
                    }
                )
        except ExtractionHarnessError as exc:
            model_calls += exc.model_calls
            failure = {
                "request_id": str(request.get("id", "unknown")),
                "section_number": str(request.get("section_number", "unknown")),
                "error": str(exc),
                "harness": {
                    "max_attempts": max_attempts,
                    "attempt_count": len(exc.attempts),
                    "attempts": exc.attempts,
                },
            }
            failures.append(failure)
            if on_progress is not None:
                on_progress(
                    {
                        "event": "section_failed",
                        "position": position,
                        "total": total,
                        "request_id": request.get("id", "unknown"),
                        "section_number": request.get("section_number", "unknown"),
                        "error": str(exc),
                        "elapsed_seconds": time.monotonic() - started_at,
                    }
                )
        except (KeyError, TypeError, ValueError, HandbookProseError) as exc:
            failure: dict[str, Any] = {
                "request_id": str(request.get("id", "unknown")),
                "section_number": str(request.get("section_number", "unknown")),
                "error": str(exc),
            }
            if raw is not None:
                failure["raw_proposal"] = raw
            failures.append(failure)
            if on_progress is not None:
                on_progress(
                    {
                        "event": "section_failed",
                        "position": position,
                        "total": total,
                        "request_id": request.get("id", "unknown"),
                        "section_number": request.get("section_number", "unknown"),
                        "error": str(exc),
                        "elapsed_seconds": time.monotonic() - started_at,
                    }
                )
    output = {
        "schema_version": SCHEMA_VERSION,
        "generation_stage": "schema_constrained_rule_proposals",
        "model": model.model,
        "verifier_model": verifier.model if verifier is not None else None,
        "direct_database_writes": False,
        "review_status": "automated",
        "results": results,
    }
    needs_review_count = sum(
        result["semantic_status"] == "needs_review" for result in results
    )
    review_counts = {
        status: sum(result.get("review_status") == status for result in results)
        for status in REVIEW_STATUSES
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "partial"
            if failures
            else "needs_review"
            if needs_review_count
            else "passed"
        ),
        "requests_attempted": len(requests),
        "model_calls": model_calls,
        "requests_validated": len(results),
        "validated_rules": validated_rule_count,
        "semantically_complete_requests": len(results) - needs_review_count,
        "requests_needing_review": needs_review_count,
        "review_counts": review_counts,
        "failures": failures,
        "database_write_attempted": False,
    }
    return output, report


def show_progress(event: dict[str, Any]) -> None:
    """Print concise, immediately flushed progress for model extraction."""

    prefix = f"[{event['position']}/{event['total']}]"
    event_type = event["event"]
    label = str(event.get("request_id", event["section_number"]))
    label = label.removeprefix("al-extraction:")
    if event_type == "section_started":
        target_label = "target" if event["target_count"] == 1 else "targets"
        if event.get("extraction_method") == "deterministic":
            message = (
                f"{prefix} Parsing {label} deterministically "
                f"({event['target_count']} {target_label})..."
            )
        else:
            message = (
                f"{prefix} Extracting {label} with "
                f"{event['model']} ({event['target_count']} {target_label})..."
            )
    elif event_type == "section_retry_started":
        message = (
            f"{prefix} Retrying unresolved clauses for "
            f"{label} with {event['model']}..."
        )
    elif event_type == "section_validation_retry":
        message = (
            f"{prefix} Validation rejected {label}; correction attempt "
            f"{event['attempt']}/{event['max_attempts']}: {event['error']}"
        )
    elif event_type == "section_retry_completed":
        message = (
            f"{prefix} Retry for {label}: "
            f"{event['retry_status']}"
        )
    elif event_type == "section_retry_failed":
        message = (
            f"{prefix} Retry failed for {label}: "
            f"{event['error']}"
        )
    elif event_type == "section_completed":
        rule_label = "rule" if event["rule_count"] == 1 else "rules"
        message = (
            f"{prefix} Completed {label}: "
            f"{event['rule_count']} {rule_label}, "
            f"{event['extraction_status']} "
            f"({event['elapsed_seconds']:.1f}s)"
        )
    else:
        message = (
            f"{prefix} Failed {label} "
            f"after {event['elapsed_seconds']:.1f}s: {event['error']}"
        )
    print(message, file=sys.stderr, flush=True)


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.is_file():
        raise HandbookProseError(f"{description} not found: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HandbookProseError(f"Invalid {description} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise HandbookProseError(f"{description} root must be an object")
    return value


def _write_json(value: dict[str, Any], output_path: Path) -> Path:
    output = output_path.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_name = temporary_file.name
        Path(temporary_name).replace(output)
    finally:
        if temporary_name is not None:
            temporary_path = Path(temporary_name)
            if temporary_path.exists():
                temporary_path.unlink()
    return output


def _load_env(path: Path | None) -> None:
    candidates = [path] if path else [Path.cwd() / ".env"]
    for candidate in candidates:
        if candidate is None or not candidate.is_file():
            continue
        for line_number, raw_line in enumerate(
            candidate.read_text(encoding="utf-8").splitlines(), start=1
        ):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            if not separator or not key.strip().isidentifier():
                raise HandbookProseError(
                    f"Invalid environment entry at {candidate}:{line_number}"
                )
            cleaned = value.strip()
            if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
                cleaned = cleaned[1:-1]
            os.environ.setdefault(key.strip(), cleaned)
        return
    if path is not None:
        raise HandbookProseError(f"Environment file not found: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse structured handbook prose and optionally propose strict A/L rules."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--graph-data", type=Path, default=DEFAULT_GRAPH_DATA)
    parser.add_argument("--structure-output", type=Path, default=DEFAULT_STRUCTURE)
    parser.add_argument("--requests-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--proposals-output", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--propose", action="store_true")
    parser.add_argument(
        "--section",
        action="append",
        default=[],
        help="Section number to propose (repeatable, e.g. --section 2.2.3.1).",
    )
    parser.add_argument(
        "--request-id",
        action="append",
        default=[],
        help=(
            "Exact extraction request ID to propose; repeat for a small batch "
            "(e.g. al-extraction:2.2.1.1:special-1)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of extraction requests to send to the API.",
    )
    parser.add_argument("--model", help="Override HANDBOOK_EXTRACTION_MODEL/OPENAI_MODEL")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Hide per-section model extraction progress.",
    )
    parser.add_argument(
        "--retry-needs-review",
        action="store_true",
        help=(
            "Make one focused API retry when unresolved text safely covers all "
            "A/L clauses in a request."
        ),
    )
    parser.add_argument(
        "--verifier-model",
        help=(
            "Independent model that re-extracts every LLM-handled unit; results "
            "are auto-accepted only when both models agree."
        ),
    )
    parser.add_argument(
        "--review-queue-output", type=Path, default=DEFAULT_REVIEW_QUEUE
    )
    parser.add_argument(
        "--only-open",
        action="store_true",
        help=(
            "Send only LLM units that are not yet auto_accepted in the existing "
            "proposals file, and merge the new results into it."
        ),
    )
    parser.add_argument(
        "--refresh-deterministic",
        action="store_true",
        help=(
            "No API calls: regenerate deterministic units in the existing "
            "proposals file and keep still-valid LLM results for the rest."
        ),
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=4,
        help="Maximum validation/correction attempts per extraction request (default: 4).",
    )
    parser.add_argument("--check-only", action="store_true")
    return parser


def _resolve(root: Path, path: Path) -> Path:
    return path.expanduser().resolve() if path.is_absolute() else (root / path).resolve()


def select_extraction_requests(
    requests: Sequence[dict[str, Any]],
    *,
    sections: Sequence[str] = (),
    request_ids: Sequence[str] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Select exact requests without silently accepting unknown filters."""

    if sections and request_ids:
        raise HandbookProseError("Section and request-ID filters cannot be combined")
    selected = list(requests)
    if request_ids:
        wanted_ids = set(request_ids)
        selected = [item for item in selected if item["id"] in wanted_ids]
        missing_ids = sorted(wanted_ids - {item["id"] for item in selected})
        if missing_ids:
            raise HandbookProseError(
                "Unknown extraction request ID(s): " + ", ".join(missing_ids)
            )
    if sections:
        wanted_sections = set(sections)
        selected = [
            item for item in selected if item["section_number"] in wanted_sections
        ]
        missing_sections = sorted(
            wanted_sections - {item["section_number"] for item in selected}
        )
        if missing_sections:
            raise HandbookProseError(
                "Unknown requested section(s): " + ", ".join(missing_sections)
            )
    if limit is not None:
        selected = selected[:limit]
    return selected


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if not 1 <= args.max_attempts <= 4:
        parser.error("--max-attempts must be between 1 and 4")
    if args.section and args.request_id:
        parser.error("--section and --request-id cannot be combined")
    if (
        args.propose
        and not args.section
        and not args.request_id
        and args.limit is None
        and not args.only_open
    ):
        parser.error(
            "--propose requires at least one --section, --request-id, or an "
            "explicit --limit"
        )

    root = args.project_root.expanduser().resolve()
    graph_path = _resolve(root, args.graph_data)
    try:
        graph_data = _load_json(graph_path, "normalized graph data")
        source_entry = next(
            (
                (source_id, checksum)
                for source_id, checksum in graph_data["source_registry"][
                    "registered_checksums"
                ].items()
                if source_id == STRUCTURED_SOURCE_ID
            ),
            None,
        )
        if source_entry is None:
            raise HandbookProseError("Structured handbook is not registered")
        handbook_source = next(
            (
                item
                for item in graph_data.get("source_registry", {}).get("sources", [])
                if item.get("id") == STRUCTURED_SOURCE_ID
            ),
            None,
        )
        source_path = "data/raw/handbook/student_handbook_english_structured.md"
        if handbook_source:
            source_path = str(handbook_source["path"])
        markdown_path = (root / source_path).resolve()
        if not markdown_path.is_file():
            raise HandbookProseError(f"Structured handbook not found: {markdown_path}")
        actual_checksum = file_sha256(markdown_path)
        if actual_checksum != source_entry[1]:
            raise HandbookProseError(
                "Structured handbook changed since registration; rerun stages 1-3"
            )
        structure, requests = parse_handbook_structure(
            markdown_path.read_text(encoding="utf-8"),
            graph_data,
            source_path=source_path,
            source_checksum=actual_checksum,
        )
        summary = structure["validation_summary"]
        print(
            f"Parsed {summary['pdf_page_markers']} page markers, "
            f"{summary['headings']} headings, and "
            f"{summary['course_sections']} A/L course sections into "
            f"{summary['extraction_units']} extraction units covering "
            f"{summary['covered_courses']} courses."
        )
        if not args.check_only:
            _write_json(structure, _resolve(root, args.structure_output))
            _write_json(requests, _resolve(root, args.requests_output))

        if args.refresh_deterministic:
            proposals_path = _resolve(root, args.proposals_output)
            merged, report, dropped = refresh_deterministic(
                _load_json(proposals_path, "existing rule proposals"),
                requests["requests"],
            )
            if not args.check_only:
                _write_json(merged, proposals_path)
                _write_json(report, _resolve(root, args.validation_output))
                _write_json(
                    build_review_queue(merged, pending_requests=requests["requests"]),
                    _resolve(root, args.review_queue_output),
                )
            print(
                f"Refreshed {len(merged['results'])} results without API calls: "
                f"{report['review_counts']}. Stale LLM results dropped: "
                f"{', '.join(dropped) or 'none'}."
            )
            return 0

        if args.propose:
            selected = select_extraction_requests(
                requests["requests"],
                sections=args.section,
                request_ids=args.request_id,
                limit=None if args.only_open else args.limit,
            )
            proposals_path = _resolve(root, args.proposals_output)
            previous = None
            if args.only_open:
                if proposals_path.is_file():
                    previous = _load_json(proposals_path, "existing rule proposals")
                selected = open_requests(selected, previous)
                if args.limit is not None:
                    selected = selected[: args.limit]
                print(
                    f"--only-open: sending {len(selected)} open unit(s): "
                    + ", ".join(item["section_number"] for item in selected)
                )
                if not selected:
                    return 0
            _load_env(args.env_file)
            needs_model = any(deterministic_proposal(item) is None for item in selected)
            client: RuleExtractionModel = (
                OpenAIHandbookExtractionClient(model=args.model)
                if needs_model
                else _DeterministicOnlyModel()
            )
            verifier = (
                OpenAIHandbookExtractionClient(model=args.verifier_model)
                if args.verifier_model and needs_model
                else None
            )
            proposals, validation = propose_rules(
                selected,
                client,
                on_progress=None if args.quiet else show_progress,
                retry_needs_review=args.retry_needs_review,
                max_attempts=args.max_attempts,
                verifier=verifier,
            )
            if args.only_open:
                run_failures = validation["failures"]
                proposals, validation, dropped = merge_proposals(
                    previous, proposals, requests["requests"]
                )
                validation["failures"] = run_failures
                print(
                    f"Merged into {len(proposals['results'])} results: "
                    f"{validation['review_counts']}. Stale results dropped: "
                    f"{', '.join(dropped) or 'none'}."
                )
            if not args.check_only:
                _write_json(proposals, proposals_path)
                _write_json(validation, _resolve(root, args.validation_output))
                _write_json(
                    build_review_queue(
                        proposals, pending_requests=requests["requests"]
                    ),
                    _resolve(root, args.review_queue_output),
                )
            print(
                f"Validated {validation['validated_rules']} proposed rules from "
                f"{validation['requests_validated']} section(s); "
                f"{validation['requests_needing_review']} section(s) need review; "
                f"{len(validation['failures'])} section(s) failed. "
                f"Overall status: {validation['status']}."
            )
        return 0
    except (OSError, UnicodeError, KeyError, HandbookProseError) as exc:
        print(f"Handbook prose extraction failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
