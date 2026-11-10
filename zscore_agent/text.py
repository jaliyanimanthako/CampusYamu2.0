"""Normalization helpers for structured inputs and database values."""

from __future__ import annotations

import re

from .constants import DISTRICTS


ACADEMIC_YEAR_RE = re.compile(r"(20\d{2})\s*[/_-]\s*(20\d{2})")
INSTITUTION_RE = re.compile(r"\(([^()]*?)\)?\s*$")
INSTITUTION_HINTS = (
    "university",
    "campus",
    "institute",
    "academy",
    "college",
    "school",
)


def normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def normalize_academic_year(value: str) -> str:
    match = ACADEMIC_YEAR_RE.search(value)
    if match is None:
        raise ValueError(f"Invalid academic year: {value}")
    return f"{match.group(1)}_{match.group(2)}"


def academic_year_start(value: str) -> int:
    return int(normalize_academic_year(value).split("_", 1)[0])


def canonical_district(value: str) -> str | None:
    normalized = normalized_text(value)
    for district in DISTRICTS:
        if normalized == normalized_text(district):
            return district
    return None


def split_course_title(title: str) -> tuple[str, str]:
    """Split ``COURSE (Institution)`` while preserving unusual course names."""

    match = INSTITUTION_RE.search(title)
    if not match:
        return title.rstrip("# ").strip(), ""
    institution = match.group(1).strip().rstrip(",").strip()
    if not any(hint in institution.casefold() for hint in INSTITUTION_HINTS):
        return title.rstrip("# ").strip(), ""
    return title[: match.start()].rstrip("# ").strip(), institution
