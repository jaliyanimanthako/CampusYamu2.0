"""Data contracts for career-trend collection and aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DIRECTIONS = {"growing", "declining", "mixed", "uncertain"}
AI_EXPOSURES = {"low", "medium", "high", "unknown"}


@dataclass(frozen=True)
class CareerTrendRequest:
    study_stream: str
    subjects: tuple[str, ...] = ()
    region: str = "global"
    max_careers: int = 10

    def __post_init__(self) -> None:
        if not self.study_stream.strip():
            raise ValueError("study_stream must not be empty")
        if not self.region.strip():
            raise ValueError("region must not be empty")
        if not 1 <= self.max_careers <= 50:
            raise ValueError("max_careers must be between 1 and 50")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["subjects"] = list(self.subjects)
        return value


@dataclass(frozen=True)
class TrendSource:
    source_id: str
    name: str
    url: str
    geography: str
    focus: str


@dataclass(frozen=True)
class CareerSignal:
    occupation: str
    direction: str
    evidence: str
    source: TrendSource
    occupation_code: str | None = None
    skills: tuple[str, ...] = ()
    related_studies: tuple[str, ...] = ()
    ai_exposure: str = "unknown"
    metric: str | None = None
    publication_date: str | None = None

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        source: TrendSource,
    ) -> "CareerSignal":
        occupation = str(payload.get("occupation") or "").strip()
        evidence = str(payload.get("evidence") or "").strip()
        if not occupation or not evidence:
            raise ValueError("signal requires occupation and evidence")
        direction = str(payload.get("direction") or "uncertain").casefold()
        ai_exposure = str(payload.get("ai_exposure") or "unknown").casefold()
        return cls(
            occupation=occupation,
            direction=direction if direction in DIRECTIONS else "uncertain",
            evidence=evidence,
            source=source,
            occupation_code=_optional_string(payload.get("occupation_code")),
            skills=_string_tuple(payload.get("skills")),
            related_studies=_string_tuple(payload.get("related_studies")),
            ai_exposure=(
                ai_exposure if ai_exposure in AI_EXPOSURES else "unknown"
            ),
            metric=_optional_string(payload.get("metric")),
            publication_date=_optional_string(payload.get("publication_date")),
        )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_string(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
