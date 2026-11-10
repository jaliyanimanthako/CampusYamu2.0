"""Deterministically merge source signals into auditable career outlooks."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

from .models import CareerSignal


DIRECTION_SCORES = {
    "growing": 2,
    "declining": -2,
    "mixed": 0,
    "uncertain": 0,
}


def aggregate_signals(
    signals: Iterable[CareerSignal],
    limit: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[CareerSignal]] = {}
    for signal in signals:
        grouped.setdefault(_career_key(signal), []).append(signal)

    careers = [_aggregate_career(items) for items in grouped.values()]
    careers.sort(
        key=lambda career: (
            career["trend_score"],
            career["source_count"],
            career["occupation"].casefold(),
        ),
        reverse=True,
    )
    return careers[:limit]


def _aggregate_career(signals: list[CareerSignal]) -> dict[str, Any]:
    signals = sorted(signals, key=lambda signal: signal.source.source_id)
    source_count = len({signal.source.source_id for signal in signals})
    directions = Counter(signal.direction for signal in signals)
    trend_score = sum(DIRECTION_SCORES[signal.direction] for signal in signals)
    disagreement = directions["growing"] > 0 and directions["declining"] > 0
    return {
        "occupation": signals[0].occupation,
        "occupation_codes": sorted(
            {signal.occupation_code for signal in signals if signal.occupation_code}
        ),
        "outlook": _outlook(trend_score, disagreement),
        "trend_score": trend_score,
        "evidence_confidence": _confidence(source_count, disagreement),
        "source_count": source_count,
        "source_disagreement": disagreement,
        "directions": dict(sorted(directions.items())),
        "ai_exposure_signals": sorted(
            {signal.ai_exposure for signal in signals if signal.ai_exposure != "unknown"}
        ),
        "skills": sorted({skill for signal in signals for skill in signal.skills}),
        "related_studies": sorted(
            {study for signal in signals for study in signal.related_studies}
        ),
        "evidence": [
            {
                "claim": signal.evidence,
                "direction": signal.direction,
                "metric": signal.metric,
                "source": signal.source.name,
                "url": signal.source.url,
                "geography": signal.source.geography,
                "publication_date": signal.publication_date,
            }
            for signal in signals
        ],
    }


def _outlook(score: int, disagreement: bool) -> str:
    if disagreement:
        return "mixed"
    if score >= 4:
        return "strong_growth"
    if score > 0:
        return "growth"
    if score < 0:
        return "caution"
    return "uncertain"


def _confidence(source_count: int, disagreement: bool) -> str:
    level = 2 if source_count >= 3 else 1 if source_count == 2 else 0
    if disagreement:
        level = max(0, level - 1)
    return ("low", "medium", "high")[level]


def _career_key(signal: CareerSignal) -> str:
    if signal.occupation_code:
        return f"code:{signal.occupation_code.casefold()}"
    return " ".join(re.findall(r"[a-z0-9]+", signal.occupation.casefold()))
