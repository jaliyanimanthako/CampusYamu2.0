"""Rules that turn statistical features into transparent labels and reasons."""

from __future__ import annotations

from collections.abc import Sequence

from .constants import CONFIDENCE_LABELS
from .models import CutoffPoint
from .statistics import robust_volatility


def has_recent_structural_jump(
    history: Sequence[CutoffPoint],
    reference_year: int | None = None,
) -> bool:
    """Flag a recent move that is large relative to the preceding history."""

    latest_year = reference_year if reference_year is not None else history[-1].year
    for index in range(2, len(history)):
        current = history[index]
        preceding_volatility = robust_volatility(history[:index])
        threshold = max(0.10, 2 * preceding_volatility)
        jump = abs(current.cutoff - history[index - 1].cutoff)
        if current.year >= latest_year - 1 and jump > threshold:
            return True
    return False


def evidence_confidence(
    *,
    history: Sequence[CutoffPoint],
    shrunk_mae: float,
    volatility: float,
    nqc_rate: float,
    is_stale: bool,
    recent_jump: bool,
) -> tuple[str, list[str]]:
    """Score evidence quality separately from the student's alignment."""

    points = 2 if len(history) >= 6 else 1 if len(history) >= 4 else 0
    factors = [f"{len(history)} numeric year(s) available"]
    if nqc_rate == 0:
        points += 1
        factors.append("No NQC years in the matched history")
    elif nqc_rate > 0.25:
        points -= 1
        factors.append("More than 25% of matched years are NQC")
    if shrunk_mae <= 0.05:
        points += 2
        factors.append("Pooled-shrunk backtest error is at most 0.05")
    elif shrunk_mae <= 0.10:
        points += 1
        factors.append("Pooled-shrunk backtest error is at most 0.10")
    else:
        factors.append("Pooled-shrunk backtest error is above 0.10")
    if volatility <= 0.10:
        points += 1
        factors.append("Robust historical volatility is at most 0.10")
    if is_stale:
        points -= 1
        factors.append("The series does not contain the database's latest year")
    if recent_jump:
        points -= 1
        factors.append("A structural jump was detected in the last two years")

    # The point ranges are: 0-1 low, 2 medium-low, 3 medium,
    # 4 medium-high, and 5 or more high.
    level = min(4, max(0, points - 1))
    return CONFIDENCE_LABELS[level], factors


def comparison_reason(
    *,
    student_score: float,
    predicted_cutoff: float,
    uncertainty: float,
    alignment: str,
    confidence: str,
    met_count: int,
    year_count: int,
) -> str:
    relation = "above" if student_score >= predicted_cutoff else "below"
    return (
        f"Historical alignment is {alignment}: the student's Z-score is "
        f"{abs(student_score - predicted_cutoff):.4f} {relation} the calibrated "
        f"cutoff estimate of {predicted_cutoff:.4f}, with ±{uncertainty:.4f} "
        f"historical uncertainty. The score met or exceeded {met_count} of "
        f"{year_count} numeric historical cutoffs. Evidence confidence is "
        f"{confidence}."
    )
