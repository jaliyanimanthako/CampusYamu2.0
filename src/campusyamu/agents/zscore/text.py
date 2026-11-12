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


# --- name-tolerant matching -------------------------------------------------------
# The published cut-off tables spell the same course differently across years
# ("APPLIED SCIENCES (PHY.SC)", "APPLIED SCIENCES PHY.SC", "PEACE & CONFLICT
# RESOLUTION"). Courses are compared by a key: normalized text with "&" read as
# "and" and the abbreviations below expanded.
COURSE_WORD_REPLACEMENTS = (
    (re.compile(r"\bphy sc\b"), "physical science"),
    (re.compile(r"\bbio sc\b"), "biological science"),
    (re.compile(r"\bfreshwater\b"), "fresh water"),
    (re.compile(r"\bagri business\b"), "agribusiness"),
    (re.compile(r"\bayurvedic\b"), "ayurveda"),
)

# Some courses publish separate cut-offs per stream:
#   "MANAGEMENT STUDIES (TV) - A [Commerce Stream]", "MANAGEMENT STUDIES TV B Any Subject",
#   "ARTS (SAB) - A * [Arts Stream]"
VARIANT_RE = re.compile(
    r"^(?P<base>.*?)\s*-?\s*\b(?P<letter>[AB])\b\s*\*?\s*"
    r"(?:\[(?P<bracket>[^\]]+)\]|(?P<plain>Commerce|Any Subject|Arts))\s*$",
    re.IGNORECASE,
)
STREAM_LABELS = {"commerce": "commerce", "arts": "arts", "any": "any"}


def variant_stream(label: str) -> str:
    text = normalized_text(label)
    if text.startswith("any"):
        return "any"
    for word, stream in STREAM_LABELS.items():
        if text.startswith(word):
            return stream
    return text


def split_course_variant(course: str) -> tuple[str, str | None, str | None]:
    """'MANAGEMENT STUDIES TV B Any Subject' -> ('MANAGEMENT STUDIES TV', 'B', 'any')."""

    match = VARIANT_RE.match(course.strip())
    if not match:
        return course, None, None
    label = match.group("bracket") or match.group("plain")
    return match.group("base").strip(), match.group("letter").upper(), variant_stream(label)


def course_key(course: str) -> str:
    text = normalized_text(course.replace("&", " and "))
    for pattern, replacement in COURSE_WORD_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


# Institution names as printed in different years -> one name per institution.
# Former names are mapped to the institution that continues them.
INSTITUTION_ALIASES = {
    "eastern university trincomalee campus": "Trincomalee Campus, Eastern University, Sri Lanka",
    "trincomalee campus eastern university sri lanka": "Trincomalee Campus, Eastern University, Sri Lanka",
    "trincomalee campus": "Trincomalee Campus, Eastern University, Sri Lanka",
    "gampaha wickramaarachchi ayurveda institute":
        "Gampaha Wickramarachchi University of Indigenous Medicine, Sri Lanka",
    "gampaha wickramarachchi ayurveda institute":
        "Gampaha Wickramarachchi University of Indigenous Medicine, Sri Lanka",
    "gampaha wickramarachchi university":
        "Gampaha Wickramarachchi University of Indigenous Medicine, Sri Lanka",
    "gampaha wickramarachchi university of indigenous medicine":
        "Gampaha Wickramarachchi University of Indigenous Medicine, Sri Lanka",
    "the gampaha wickramarachchi university of indigenous medicine sri lanka":
        "Gampaha Wickramarachchi University of Indigenous Medicine, Sri Lanka",
    "university of colombo sri palee campus": "Sripalee Campus",
    "sripalee campus university of colombo": "Sripalee Campus",
    "university of jaffna vavuniya campus": "University of Vavuniya, Sri Lanka",   # elevated 2021
    "university of jayewardenepura": "University of Sri Jayewardenepura",
    "university of sabaragamuwa": "Sabaragamuwa University of Sri Lanka",
    "swami vipulananda institute of aesthetic studies": "Swamy Vipulananda Institute of Aesthetic Studies",
    "swamy vipulananda institute of aesthetic studies eastern university sri lanka":
        "Swamy Vipulananda Institute of Aesthetic Studies",
    "institute of indigenous medicine": "University of Colombo",        # an institute of the University of Colombo
    "ramanathan academy of fine arts": "University of Jaffna",          # a unit of the University of Jaffna
}


def canonical_institution(name: str) -> str:
    return INSTITUTION_ALIASES.get(normalized_text(name or ""), (name or "").strip())
