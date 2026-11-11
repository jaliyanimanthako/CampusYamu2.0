"""Shape, prioritize, and label collected web documents."""

from __future__ import annotations

from typing import Any

from .models import WebDocument
from .source_registry import is_excluded


TIER_ORDER = {
    "local_official": 0,
    "local_professional_body": 1,
    "local_live_jobs": 2,
    "global_official": 3,
    "global_outlook": 4,
    "community_discussion": 5,
    "other": 6,
}
QUERY_ORDER = {
    "local_live_jobs": 0,
    "local_market": 1,
    "local_challenges": 2,
    "global_outlook": 3,
    "international_pathways": 4,
    "further_study": 5,
    "emerging_specialisations": 6,
    "field_sources": 7,
    "career_paths": 8,
    "community_signals": 9,
}


def deduplicate(documents: list[WebDocument]) -> list[WebDocument]:
    ordered = sorted(
        documents,
        key=lambda item: (
            QUERY_ORDER.get(item.query_category, 99),
            not item.trusted,
            TIER_ORDER.get(item.source_tier, 99),
            item.domain,
            item.url,
        ),
    )
    unique: dict[str, WebDocument] = {}
    for document in ordered:
        if not is_excluded(document.domain):
            unique.setdefault(document.url, document)
    return list(unique.values())


def select_documents(
    documents: list[WebDocument],
    limit: int,
) -> list[WebDocument]:
    """Round-robin categories so opportunity pages cannot hide risk evidence."""

    buckets: dict[str, list[WebDocument]] = {}
    for document in deduplicate(documents):
        buckets.setdefault(document.query_category, []).append(document)
    categories = sorted(buckets, key=lambda value: QUERY_ORDER.get(value, 99))
    selected = []
    while len(selected) < limit and any(buckets.values()):
        for category in categories:
            if buckets[category] and len(selected) < limit:
                selected.append(buckets[category].pop(0))
    return selected


def document_dict(document: WebDocument, content_limit: int) -> dict[str, Any]:
    value = document.to_dict()
    value["markdown"] = document.markdown[:content_limit]
    value["content_truncated"] = len(document.markdown) > content_limit
    return value


def course_status(
    documents: list[WebDocument],
    failures: list[dict[str, str]],
) -> str:
    if documents and failures:
        return "partial_failure"
    if documents:
        return "success"
    return "failed"


def overall_status(course_research: list[dict[str, Any]]) -> str:
    statuses = {item["status"] for item in course_research}
    if statuses == {"success"}:
        return "success"
    if statuses == {"failed"}:
        return "failed"
    return "partial_failure"
