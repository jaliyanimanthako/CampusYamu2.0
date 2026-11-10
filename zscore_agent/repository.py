"""Read-only access to historical cutoff records."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .constants import DEFAULT_DATABASE_PATH, DISTRICTS
from .models import CutoffPoint, ZScoreRequest
from .text import (
    academic_year_start,
    canonical_district,
    normalized_text,
    split_course_title,
)


class SQLScoreStore:
    """Retrieve application-owned, parameterized queries from SQLite."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        if not self.database_path.is_file():
            raise FileNotFoundError(f"Z-score database not found: {self.database_path}")
        required_columns = {"academic_year", "Course of Study", *DISTRICTS}
        missing_columns = sorted(required_columns - self._read_columns())
        if missing_columns:
            raise ValueError(
                "The z_scores_all table is missing required columns: "
                + ", ".join(missing_columns)
            )

    def fetch_history(self, request: ZScoreRequest) -> dict[str, Any]:
        """Return every published year for a course and applicant district."""

        district = canonical_district(request.district)
        if district is None:
            return self._result(
                request,
                status="invalid_district",
                message=f"Unknown Sri Lankan district: {request.district}.",
            )

        # District is interpolated only after validation against the fixed allowlist.
        sql = (
            f'SELECT academic_year, "Course of Study", "{district}" AS cutoff '
            'FROM z_scores_all '
            'WHERE lower("Course of Study") LIKE ? ESCAPE \'\\\' '
            'ORDER BY academic_year, "Course of Study"'
        )
        course_pattern = f"%{self._escape_like(request.course.casefold())}%"
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, (course_pattern,)).fetchall()

        wanted_course = normalized_text(request.course)
        matches: list[dict[str, str]] = []
        for row in rows:
            course, institution = split_course_title(str(row["Course of Study"]))
            if normalized_text(course) != wanted_course:
                continue
            cutoff = row["cutoff"]
            if cutoff is None or not str(cutoff).strip():
                continue
            matches.append(
                {
                    "academic_year": str(row["academic_year"]),
                    "course": course,
                    "institution": institution,
                    "district": district.title(),
                    "z_score": str(cutoff).strip(),
                    "source_table": "z_scores_all",
                }
            )

        if not matches:
            return self._result(
                request,
                status="not_found",
                message=(
                    f"No {request.course} cutoff history was found for "
                    f"{district.title()} district."
                ),
            )
        return self._result(
            request,
            status="success",
            message=(
                f"Found {len(matches)} historical {request.course} cutoff record(s) "
                f"for {district.title()} district."
            ),
            matches=matches,
        )

    @property
    def academic_years(self) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT academic_year
                FROM z_scores_all
                WHERE academic_year IS NOT NULL
                ORDER BY academic_year
                """
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def all_numeric_histories(self) -> tuple[tuple[CutoffPoint, ...], ...]:
        """Load usable histories for one global forecast calibration."""

        district_columns = ", ".join(f'"{district}"' for district in DISTRICTS)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f'SELECT academic_year, "Course of Study", {district_columns} '
                'FROM z_scores_all ORDER BY academic_year, "Course of Study"'
            ).fetchall()

        grouped: dict[tuple[str, str, str], list[CutoffPoint]] = {}
        for row in rows:
            course, institution = split_course_title(str(row["Course of Study"]))
            academic_year = str(row["academic_year"])
            year = academic_year_start(academic_year)
            for district in DISTRICTS:
                try:
                    cutoff = float(row[district])
                except (TypeError, ValueError):
                    continue
                series_key = (course, institution, district)
                grouped.setdefault(series_key, []).append(
                    CutoffPoint(year, academic_year, cutoff)
                )
        return tuple(
            tuple(sorted(history))
            for history in grouped.values()
            if len(history) >= 3
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path.as_uri() + "?mode=ro",
            uri=True,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    def _read_columns(self) -> set[str]:
        with closing(self._connect()) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                ("z_scores_all",),
            ).fetchone()
            if table is None:
                raise ValueError("The database does not contain a z_scores_all table.")
            return {
                str(row[1])
                for row in connection.execute('PRAGMA table_info("z_scores_all")')
            }

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _result(
        self,
        request: ZScoreRequest,
        *,
        status: str,
        message: str,
        matches: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "message": message,
            "input": request.to_dict(),
            "matches": matches or [],
            "source": {
                "database": str(self.database_path),
                "table": "z_scores_all",
                "read_only": True,
            },
        }
