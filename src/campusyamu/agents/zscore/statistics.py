"""Pure statistical helpers with no database or agent dependencies."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from .models import CutoffPoint
from .text import academic_year_start


def _coordinates(
    history: Sequence[CutoffPoint] | Sequence[tuple[str, float]],
) -> tuple[list[float], list[float]]:
    if not history:
        return [], []
    first = history[0]
    if isinstance(first, CutoffPoint):
        points = history  # type: ignore[assignment]
        return (
            [float(point.year) for point in points],
            [point.cutoff for point in points],
        )
    pairs = history  # type: ignore[assignment]
    return (
        [float(academic_year_start(year)) for year, _ in pairs],
        [float(cutoff) for _, cutoff in pairs],
    )


def trend_slope(
    history: Sequence[CutoffPoint] | Sequence[tuple[str, float]],
) -> float:
    """Return the least-squares cutoff change per actual academic year."""

    years, cutoffs = _coordinates(history)
    if len(years) < 2:
        return 0.0
    year_mean = statistics.fmean(years)
    cutoff_mean = statistics.fmean(cutoffs)
    denominator = sum((year - year_mean) ** 2 for year in years)
    if denominator == 0:
        return 0.0
    return sum(
        (year - year_mean) * (cutoff - cutoff_mean)
        for year, cutoff in zip(years, cutoffs)
    ) / denominator


def theil_sen_slope(history: Sequence[CutoffPoint]) -> float:
    """Return the median pairwise slope, which is resistant to one bad year."""

    slopes = [
        (right.cutoff - left.cutoff) / (right.year - left.year)
        for index, left in enumerate(history)
        for right in history[index + 1 :]
        if right.year != left.year
    ]
    return statistics.median(slopes) if slopes else 0.0


def year_weighted_mean(history: Sequence[CutoffPoint]) -> float:
    """Weight observations by elapsed year so gaps do not shift the weights."""

    if not history:
        raise ValueError("history must contain at least one point")
    first_year = history[0].year
    weights = [point.year - first_year + 1 for point in history]
    return sum(
        point.cutoff * weight for point, weight in zip(history, weights)
    ) / sum(weights)


def robust_volatility(history: Sequence[CutoffPoint]) -> float:
    """Return MAD scaled to the same units as standard deviation and MAE."""

    if len(history) < 2:
        return 0.0
    median = statistics.median(point.cutoff for point in history)
    mad = statistics.median(abs(point.cutoff - median) for point in history)
    return 1.4826 * mad


def classify_historical_alignment(alignment_score: float) -> str:
    if alignment_score >= 1.0:
        return "high"
    if alignment_score >= 0.25:
        return "medium_high"
    if alignment_score > -0.25:
        return "medium"
    if alignment_score > -1.0:
        return "medium_low"
    return "low"
