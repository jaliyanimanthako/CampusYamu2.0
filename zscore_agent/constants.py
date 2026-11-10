"""Shared constants for the Z-score agent."""

from __future__ import annotations

import sys
from pathlib import Path


_SOURCE_DATABASE_PATH = Path(__file__).parents[1] / "data" / "z_scores.db"
_INSTALLED_DATABASE_PATH = (
    Path(sys.prefix) / "share" / "campusselection" / "z_scores.db"
)
DEFAULT_DATABASE_PATH = (
    _SOURCE_DATABASE_PATH
    if _SOURCE_DATABASE_PATH.is_file()
    else _INSTALLED_DATABASE_PATH
)
DISTRICTS = (
    "COLOMBO",
    "GAMPAHA",
    "KALUTARA",
    "MATALE",
    "KANDY",
    "NUWARA ELIYA",
    "GALLE",
    "MATARA",
    "HAMBANTOTA",
    "JAFFNA",
    "KILINOCHCHI",
    "MANNAR",
    "MULLAITIVU",
    "VAVUNIYA",
    "TRINCOMALEE",
    "BATTICALOA",
    "AMPARA",
    "PUTTALAM",
    "KURUNEGALA",
    "ANURADHAPURA",
    "POLONNARUWA",
    "BADULLA",
    "MONARAGALA",
    "KEGALLE",
    "RATNAPURA",
)

CONFIDENCE_LABELS = (
    "low",
    "medium_low",
    "medium",
    "medium_high",
    "high",
)

FORECAST_METHODS = (
    "latest",
    "year_weighted_mean",
    "damped_linear_trend",
    "damped_theil_sen_trend",
)
