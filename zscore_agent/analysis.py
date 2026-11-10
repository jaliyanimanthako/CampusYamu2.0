"""Orchestrate deterministic historical comparisons."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Sequence

from .constants import CONFIDENCE_LABELS
from .forecasting import fit_calibration
from .models import CalibrationProfile, ZScoreRequest
from .reporting import build_report
from .repository import SQLScoreStore
from .text import academic_year_start, canonical_district


class HistoricalAnalyzer:
    """Retrieve histories and coordinate calibrated report generation."""

    def __init__(self, store: SQLScoreStore) -> None:
        self.store = store
        self._calibration: CalibrationProfile | None = None

    @property
    def calibration(self) -> CalibrationProfile:
        if self._calibration is None:
            all_histories = self.store.all_numeric_histories()
            self._calibration = fit_calibration(all_histories)
        return self._calibration

    def analyze(
        self,
        request: ZScoreRequest,
        report_limit: int,
    ) -> dict[str, Any]:
        evidence = self.store.fetch_history(request)
        if evidence["status"] != "success":
            return {
                **evidence,
                "analysis_method": "calibrated_historical_comparison",
                "reports": [],
                "total_reports": 0,
            }

        district = canonical_district(request.district)
        assert district is not None  # The repository validated it.
        database_latest_year = academic_year_start(self.store.academic_years[-1])
        grouped_matches = self._group_by_institution(evidence["matches"])
        reports = []
        for (course, institution), matches in grouped_matches.items():
            report = build_report(
                course=course,
                institution=institution,
                district=district,
                student_score=request.z_score,
                matches=matches,
                database_latest_year=database_latest_year,
                calibration=self.calibration,
            )
            if report is not None:
                reports.append(report)

        self._sort_reports(reports)
        total_reports = len(reports)
        reports = reports[:report_limit]
        return {
            "status": "success" if reports else "insufficient_data",
            "message": (
                f"Generated {total_reports} historical comparison report(s) for "
                f"{request.course} in {district.title()} district."
                if reports
                else "No numeric cutoff history is available for this selection."
            ),
            "input": request.to_dict(),
            "analysis_method": "calibrated_historical_comparison",
            "disclaimer": (
                "Historical alignment is not an admission probability or a guarantee "
                "of selection."
            ),
            "calibration": self._rounded_calibration(),
            "reports": reports,
            "total_reports": total_reports,
            "truncated": total_reports > len(reports),
            "source": evidence["source"],
        }

    @staticmethod
    def _group_by_institution(
        matches: Sequence[dict[str, str]],
    ) -> dict[tuple[str, str], list[dict[str, str]]]:
        grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
        for match in matches:
            series_key = (match["course"], match["institution"])
            grouped.setdefault(series_key, []).append(match)
        return grouped

    @staticmethod
    def _sort_reports(reports: list[dict[str, Any]]) -> None:
        label_rank = {label: index for index, label in enumerate(CONFIDENCE_LABELS)}
        reports.sort(
            key=lambda report: (
                label_rank[report["historical_alignment"]],
                label_rank[report["evidence_confidence"]],
                report["comparison"]["expected_margin"],
            ),
            reverse=True,
        )

    def _rounded_calibration(self) -> dict[str, Any]:
        calibration = asdict(self.calibration)
        for key in ("pooled_mae", "uncertainty_multiplier", "observed_coverage"):
            calibration[key] = round(calibration[key], 4)
        return calibration
