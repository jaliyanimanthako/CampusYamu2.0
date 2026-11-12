"""Small data models passed between the agent modules."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ZScoreRequest:
    """The complete input contract exposed to the parent agent."""

    district: str
    course: str
    z_score: float
    stream: str | None = None      # picks stream-specific cut-offs (e.g. Management Studies (TV) A/B)

    def __post_init__(self) -> None:
        if not self.district.strip():
            raise ValueError("district must not be empty")
        if not self.course.strip():
            raise ValueError("course must not be empty")
        if not math.isfinite(self.z_score):
            raise ValueError("z_score must be a finite number")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["stream"] is None:
            del data["stream"]
        return data


@dataclass(frozen=True, order=True)
class CutoffPoint:
    """One numeric cutoff tied to its actual starting academic year."""

    year: int
    academic_year: str
    cutoff: float


@dataclass(frozen=True)
class CalibrationProfile:
    """Forecast settings learned from pooled historical backtests."""

    method: str
    pooled_mae: float
    uncertainty_multiplier: float
    target_coverage: float
    observed_coverage: float
    backtest_count: int
