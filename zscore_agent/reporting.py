"""Build one serializable historical comparison report."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

from .assessment import (
    comparison_reason,
    evidence_confidence,
    has_recent_structural_jump,
)
from .forecasting import forecast_cutoff, series_uncertainty
from .models import CalibrationProfile, CutoffPoint
from .statistics import (
    classify_historical_alignment,
    robust_volatility,
    trend_slope,
    year_weighted_mean,
)
from .text import academic_year_start


def build_report(
    *,
    course: str,
    institution: str,
    district: str,
    student_score: float,
    matches: Sequence[dict[str, str]],
    database_latest_year: int,
    calibration: CalibrationProfile,
) -> dict[str, Any] | None:
    history, nqc_years = split_history(matches)
    if not history:
        return None

    forecast_year = database_latest_year + 1
    predicted_cutoff = forecast_cutoff(history, calibration.method, forecast_year)
    uncertainty, own_mae, shrunk_mae = series_uncertainty(history, calibration)
    expected_margin = student_score - predicted_cutoff
    alignment_score = expected_margin / uncertainty
    historical_alignment = classify_historical_alignment(alignment_score)
    volatility = robust_volatility(history)
    recent_jump = has_recent_structural_jump(history, database_latest_year)
    is_stale = history[-1].year < database_latest_year
    nqc_rate = len(nqc_years) / (len(history) + len(nqc_years))
    confidence, factors = evidence_confidence(
        history=history,
        shrunk_mae=shrunk_mae,
        volatility=volatility,
        nqc_rate=nqc_rate,
        is_stale=is_stale,
        recent_jump=recent_jump,
    )
    met_count = sum(student_score >= point.cutoff for point in history)
    cutoffs = [point.cutoff for point in history]

    return {
        "course": course,
        "institution": institution,
        "district": district.title(),
        "student_z_score": round(student_score, 4),
        "historical_summary": {
            "latest_academic_year": history[-1].academic_year,
            "latest_cutoff": round(history[-1].cutoff, 4),
            "mean_cutoff": round(statistics.fmean(cutoffs), 4),
            "median_cutoff": round(statistics.median(cutoffs), 4),
            "year_weighted_cutoff": round(year_weighted_mean(history), 4),
            "minimum_cutoff": round(min(cutoffs), 4),
            "maximum_cutoff": round(max(cutoffs), 4),
            "trend_slope": round(trend_slope(history), 4),
            "robust_volatility": round(volatility, 4),
        },
        "comparison": {
            "forecast_academic_year": f"{forecast_year}_{forecast_year + 1}",
            "predicted_cutoff": round(predicted_cutoff, 4),
            "uncertainty": round(uncertainty, 4),
            "range_lower": round(predicted_cutoff - uncertainty, 4),
            "range_upper": round(predicted_cutoff + uncertainty, 4),
            "expected_margin": round(expected_margin, 4),
            "alignment_score": round(alignment_score, 4),
            "years_met_or_exceeded": met_count,
            "years_compared": len(history),
        },
        "historical_alignment": historical_alignment,
        "evidence_confidence": confidence,
        "confidence_factors": factors,
        "reliability": {
            "selected_method": calibration.method,
            "own_backtest_mae": round(own_mae, 4) if own_mae is not None else None,
            "pooled_shrunk_mae": round(shrunk_mae, 4),
            "numeric_years": len(history),
            "nqc_years": len(nqc_years),
            "nqc_rate": round(nqc_rate, 4),
            "is_stale": is_stale,
            "recent_structural_jump": recent_jump,
        },
        "history": history_rows(history, nqc_years),
        "reason": comparison_reason(
            student_score=student_score,
            predicted_cutoff=predicted_cutoff,
            uncertainty=uncertainty,
            alignment=historical_alignment,
            confidence=confidence,
            met_count=met_count,
            year_count=len(history),
        ),
    }


def split_history(
    matches: Sequence[dict[str, str]],
) -> tuple[list[CutoffPoint], list[str]]:
    history: list[CutoffPoint] = []
    nqc_years: list[str] = []
    for match in matches:
        try:
            cutoff = float(match["z_score"])
        except (TypeError, ValueError):
            if match["z_score"].casefold() == "nqc":
                nqc_years.append(match["academic_year"])
            continue
        history.append(
            CutoffPoint(
                academic_year_start(match["academic_year"]),
                match["academic_year"],
                cutoff,
            )
        )
    return sorted(history), sorted(set(nqc_years))


def history_rows(
    history: Sequence[CutoffPoint],
    nqc_years: Sequence[str],
) -> list[dict[str, Any]]:
    rows = [
        {
            "academic_year": point.academic_year,
            "cutoff": round(point.cutoff, 4),
            "status": "numeric",
        }
        for point in history
    ]
    rows.extend(
        {"academic_year": year, "cutoff": None, "status": "NQC"}
        for year in nqc_years
    )
    return sorted(rows, key=lambda row: row["academic_year"])
