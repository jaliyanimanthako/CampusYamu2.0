"""Prepare evidence for the LLM and validate its citations."""

from __future__ import annotations

from typing import Any


SWOT_CATEGORIES = ("strengths", "weaknesses", "opportunities", "threats")


def build_evidence_packet(
    course: dict[str, Any],
    *,
    max_documents: int,
    max_content_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents = course.get("documents")
    if not isinstance(documents, list):
        return [], []
    candidates = []
    for number, document in enumerate(documents[:max_documents], start=1):
        if not isinstance(document, dict):
            continue
        content = str(document.get("markdown") or "").strip()
        if not content:
            # Blocked pages (e.g. Reddit via Firecrawl) still carry a snippet.
            snippet = str(document.get("description") or "").strip()
            content = f"[Search snippet only; page not scraped]\n{snippet}" if snippet else ""
        if content:
            candidates.append((number, document, content))

    # Share the budget fairly so late sources (often risk or community
    # evidence) are not crowded out by long early pages.
    limits = _fair_shares([len(content) for _, _, content in candidates], max_content_chars)
    evidence = []
    evidence_index = []
    for (number, document, content), limit in zip(candidates, limits):
        content = content[:limit]
        if not content.strip():
            continue
        evidence_id = f"E{number:03d}"
        shared = {
            "evidence_id": evidence_id,
            "title": str(document.get("title") or ""),
            "url": str(document.get("url") or ""),
            "source_tier": str(document.get("source_tier") or "other"),
            "trusted": bool(document.get("trusted")),
            "query_category": str(document.get("query_category") or ""),
        }
        evidence.append({**shared, "content": content})
        evidence_index.append(shared)
    return evidence, evidence_index


def cap_unverified_confidence(analysis: dict[str, Any], trusted_ids: set[str]) -> int:
    """Downgrade 'high' to 'medium' when no cited source is trusted.

    Several unverified pages agreeing is not the same as official evidence,
    and models tend to over-rate that kind of agreement. Returns how many
    ratings were lowered.
    """

    items = [
        finding
        for category in SWOT_CATEGORIES
        for finding in analysis.get("future_swot", {}).get(category, [])
    ]
    outlook = analysis.get("overall_outlook")
    if isinstance(outlook, dict):
        items.append(outlook)
    lowered = 0
    for item in items:
        if item.get("confidence") == "high" and not set(item.get("evidence_refs", [])) & trusted_ids:
            item["confidence"] = "medium"
            lowered += 1
    return lowered


def _fair_shares(lengths: list[int], budget: int) -> list[int]:
    """Give short documents what they need and split the rest evenly."""

    shares = [0] * len(lengths)
    remaining = max(0, budget)
    order = sorted(range(len(lengths)), key=lambda index: lengths[index])
    for position, index in enumerate(order):
        share = remaining // (len(order) - position)
        shares[index] = min(lengths[index], share)
        remaining -= shares[index]
    return shares


def validate_evidence_refs(analysis: dict[str, Any], valid_ids: set[str]) -> None:
    themes = analysis.get("evidence_synthesis")
    if not isinstance(themes, list):
        raise RuntimeError("Analytics response has no evidence_synthesis list")
    for theme in themes:
        refs = theme.get("evidence_refs") if isinstance(theme, dict) else None
        invalid = set(refs or []) - valid_ids
        if not refs or invalid:
            raise RuntimeError(f"A synthesis theme has missing or unknown evidence: {sorted(invalid)}")
    swot = analysis.get("future_swot")
    if not isinstance(swot, dict):
        raise RuntimeError("Analytics response has no future_swot object")
    for category in SWOT_CATEGORIES:
        findings = swot.get(category)
        if not isinstance(findings, list):
            raise RuntimeError(f"Analytics response has invalid {category}")
        for finding in findings:
            refs = finding.get("evidence_refs") if isinstance(finding, dict) else None
            if not isinstance(refs, list) or not refs:
                raise RuntimeError(f"A {category} finding has no evidence references")
            invalid = set(refs) - valid_ids
            if invalid:
                raise RuntimeError(
                    f"A {category} finding cited unknown evidence: {sorted(invalid)}"
                )
    for verdict_name in ("course_introduction", "local_vs_overseas", "further_study"):
        verdict = analysis.get(verdict_name)
        if not isinstance(verdict, dict):
            raise RuntimeError(f"Analytics response has no {verdict_name} verdict")
        invalid = set(verdict.get("evidence_refs") or []) - valid_ids
        if invalid:
            raise RuntimeError(
                f"The {verdict_name} verdict cited unknown evidence: {sorted(invalid)}"
            )
    niches = analysis.get("niche_specialisations")
    if not isinstance(niches, list):
        raise RuntimeError("Analytics response has no niche_specialisations list")
    for niche in niches:
        refs = niche.get("evidence_refs") if isinstance(niche, dict) else None
        invalid = set(refs or []) - valid_ids
        if not refs or invalid:
            raise RuntimeError(
                f"A niche specialisation has missing or unknown evidence: {sorted(invalid)}"
            )
    outlook = analysis.get("overall_outlook")
    refs = outlook.get("evidence_refs") if isinstance(outlook, dict) else None
    if not isinstance(refs, list) or not refs:
        raise RuntimeError("The overall outlook has no evidence references")
    invalid = set(refs) - valid_ids
    if invalid:
        raise RuntimeError(
            f"The overall outlook cited unknown evidence: {sorted(invalid)}"
        )
