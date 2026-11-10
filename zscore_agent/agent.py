"""Public interface for deterministic Z-score analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analysis import HistoricalAnalyzer
from .constants import DEFAULT_DATABASE_PATH
from .models import ZScoreRequest
from .repository import SQLScoreStore


class ZScoreAgent:
    """Analyze one course, district, and student Z-score."""

    def __init__(
        self,
        database_path: str | Path = DEFAULT_DATABASE_PATH,
    ) -> None:
        self.store = SQLScoreStore(database_path)
        self.analyzer = HistoricalAnalyzer(self.store)

    def analyze(
        self,
        *,
        district: str,
        course: str,
        z_score: float,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Run the complete deterministic workflow from three explicit inputs."""

        request = ZScoreRequest(district=district, course=course, z_score=z_score)
        return self.evaluate(request, limit=limit)

    def evaluate(
        self,
        request: ZScoreRequest,
        *,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Accept a request object when called by a parent agent."""

        if limit < 1:
            raise ValueError("limit must be at least 1")
        return self.analyzer.analyze(request, report_limit=limit)

    @staticmethod
    def format_answer(result: dict[str, Any]) -> str:
        lines = [str(result["message"])]
        if result.get("disclaimer"):
            lines.append(str(result["disclaimer"]))
        for report in result.get("reports", []):
            summary = report["historical_summary"]
            comparison = report["comparison"]
            institution = report["institution"] or "Unspecified institution"
            lines.extend(
                [
                    "",
                    f"{report['course']} — {institution}",
                    f"Historical alignment: {report['historical_alignment']}",
                    f"Evidence confidence: {report['evidence_confidence']}",
                    f"Latest cutoff: {summary['latest_cutoff']:.4f} "
                    f"({summary['latest_academic_year'].replace('_', '/')})",
                    f"Calibrated estimate: {comparison['predicted_cutoff']:.4f} "
                    f"± {comparison['uncertainty']:.4f}",
                    f"Expected margin: {comparison['expected_margin']:+.4f}",
                    f"Met or exceeded {comparison['years_met_or_exceeded']} of "
                    f"{comparison['years_compared']} numeric historical cutoffs.",
                ]
            )
        if result.get("truncated"):
            lines.append(
                f"Showing {len(result['reports'])} of {result['total_reports']} reports."
            )
        return "\n".join(lines)
