"""Data contracts for course-scoped web collection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class WebResearchRequest:
    courses: tuple[str, ...]
    region: str = "Sri Lanka"
    results_per_query: int = 3
    max_sources_per_course: int = 20
    content_char_limit: int = 8_000

    def __post_init__(self) -> None:
        normalized_courses = _unique_strings(self.courses)
        if not normalized_courses:
            raise ValueError("courses must contain at least one course")
        if len(normalized_courses) > 20:
            raise ValueError("courses must contain at most 20 courses")
        if not self.region.strip():
            raise ValueError("region must not be empty")
        if not 1 <= self.results_per_query <= 10:
            raise ValueError("results_per_query must be between 1 and 10")
        if not 1 <= self.max_sources_per_course <= 50:
            raise ValueError("max_sources_per_course must be between 1 and 50")
        if not 500 <= self.content_char_limit <= 50_000:
            raise ValueError("content_char_limit must be between 500 and 50000")
        object.__setattr__(self, "courses", normalized_courses)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["courses"] = list(self.courses)
        return value


@dataclass(frozen=True)
class CourseProfile:
    name: str
    category: str
    focus_areas: tuple[str, ...]
    mapped: bool
    # Small, growing specialisations inside the profession (e.g. whole-life
    # carbon assessment for quantity surveying), found by career discovery.
    emerging_areas: tuple[str, ...] = ()


@dataclass(frozen=True)
class SearchQuery:
    category: str
    text: str
    source_types: tuple[str, ...] = ("web",)
    variants: tuple[str, ...] = ()
    include_domains: tuple[str, ...] = ()
    time_range: str | None = None  # day | week | month | year
    country: str | None = None  # boosts results from this country


@dataclass(frozen=True)
class WebDocument:
    """Raw page content returned by Firecrawl search-and-scrape."""

    url: str
    title: str
    description: str
    markdown: str
    query: str
    query_category: str
    result_type: str
    domain: str
    source_tier: str
    trusted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unique_strings(values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (tuple, list)):
        return ()
    unique: dict[str, str] = {}
    for value in values:
        text = str(value).strip()
        if text:
            unique.setdefault(text.casefold(), text)
    return tuple(unique.values())
