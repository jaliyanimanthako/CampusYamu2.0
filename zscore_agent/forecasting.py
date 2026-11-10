"""Small-sample forecasting and pooled uncertainty calibration."""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from .constants import FORECAST_METHODS
from .models import CalibrationProfile, CutoffPoint
from .statistics import (
    robust_volatility,
    theil_sen_slope,
    trend_slope,
    year_weighted_mean,
)


MINIMUM_TRAINING_POINTS = 3
TREND_DAMPING = 0.5
MAXIMUM_ANNUAL_CHANGE = 0.15
UNCERTAINTY_FLOOR = 0.05
PRIOR_ERROR_STRENGTH = 3
TARGET_COVERAGE = 0.80


def forecast_cutoff(
    history: Sequence[CutoffPoint],
    method: str,
    target_year: int | None = None,
) -> float:
    """Forecast one cutoff with a simple, bounded method."""

    if not history:
        raise ValueError("history must contain at least one point")
    if method == "latest":
        return history[-1].cutoff
    if method == "year_weighted_mean":
        return year_weighted_mean(history)
    if method not in FORECAST_METHODS:
        raise ValueError(f"Unknown forecast method: {method}")

    raw_slope = (
        trend_slope(history)
        if method == "damped_linear_trend"
        else theil_sen_slope(history)
    )
    annual_change = max(
        -MAXIMUM_ANNUAL_CHANGE,
        min(MAXIMUM_ANNUAL_CHANGE, TREND_DAMPING * raw_slope),
    )
    forecast_year = target_year if target_year is not None else history[-1].year + 1
    years_ahead = max(1, forecast_year - history[-1].year)
    return history[-1].cutoff + annual_change * years_ahead


def backtest_errors(
    history: Sequence[CutoffPoint],
    method: str,
) -> tuple[float, ...]:
    errors = []
    for target_index in range(MINIMUM_TRAINING_POINTS, len(history)):
        training = history[:target_index]
        actual = history[target_index]
        prediction = forecast_cutoff(training, method, actual.year)
        errors.append(abs(actual.cutoff - prediction))
    return tuple(errors)


def fit_calibration(
    histories: Sequence[Sequence[CutoffPoint]],
) -> CalibrationProfile:
    """Choose one global method and calibrate its uncertainty across all series."""

    method_errors = {
        method: [
            error
            for history in histories
            for error in backtest_errors(history, method)
        ]
        for method in FORECAST_METHODS
    }
    usable = {method: errors for method, errors in method_errors.items() if errors}
    if not usable:
        return CalibrationProfile("latest", 0.10, 1.0, TARGET_COVERAGE, 0.0, 0)

    selected_method = min(usable, key=lambda name: statistics.fmean(usable[name]))
    pooled_errors = usable[selected_method]
    pooled_mae = statistics.fmean(pooled_errors)
    calibration_rows: list[tuple[float, float]] = []

    for history in histories:
        previous_errors: list[float] = []
        for target_index in range(MINIMUM_TRAINING_POINTS, len(history)):
            training = history[:target_index]
            actual = history[target_index]
            prediction = forecast_cutoff(training, selected_method, actual.year)
            error = abs(actual.cutoff - prediction)
            own_mae = (
                statistics.fmean(previous_errors) if previous_errors else pooled_mae
            )
            shrunk_mae = _shrink_mae(
                own_mae, len(previous_errors), pooled_mae
            )
            raw_uncertainty = max(
                shrunk_mae,
                robust_volatility(training),
                UNCERTAINTY_FLOOR,
            )
            calibration_rows.append((error, raw_uncertainty))
            previous_errors.append(error)

    ratios = [error / uncertainty for error, uncertainty in calibration_rows]
    multiplier = max(1.0, _percentile(ratios, TARGET_COVERAGE))
    observed_coverage = sum(
        error <= uncertainty * multiplier
        for error, uncertainty in calibration_rows
    ) / len(calibration_rows)
    return CalibrationProfile(
        method=selected_method,
        pooled_mae=pooled_mae,
        uncertainty_multiplier=multiplier,
        target_coverage=TARGET_COVERAGE,
        observed_coverage=observed_coverage,
        backtest_count=len(pooled_errors),
    )


def series_uncertainty(
    history: Sequence[CutoffPoint],
    profile: CalibrationProfile,
) -> tuple[float, float | None, float]:
    """Return calibrated uncertainty, own MAE, and pooled-shrunk MAE."""

    errors = backtest_errors(history, profile.method)
    own_mae = statistics.fmean(errors) if errors else None
    shrunk_mae = _shrink_mae(
        own_mae if own_mae is not None else profile.pooled_mae,
        len(errors),
        profile.pooled_mae,
    )
    raw_uncertainty = max(
        shrunk_mae,
        robust_volatility(history),
        UNCERTAINTY_FLOOR,
    )
    return (
        raw_uncertainty * profile.uncertainty_multiplier,
        own_mae,
        shrunk_mae,
    )


def _shrink_mae(own_mae: float, error_count: int, pooled_mae: float) -> float:
    return (
        error_count * own_mae + PRIOR_ERROR_STRENGTH * pooled_mae
    ) / (error_count + PRIOR_ERROR_STRENGTH)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    remainder = position - lower_index
    return (
        ordered[lower_index] * (1 - remainder)
        + ordered[upper_index] * remainder
    )
