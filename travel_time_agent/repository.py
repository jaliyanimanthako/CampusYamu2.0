"""Read-only queries over ``data/travel_times.db``."""

from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_db import DEFAULT_DB


class LookupError_(LookupError):
    """A DS division / university that cannot be resolved, with suggestions."""

    def __init__(self, message: str, suggestions: list[str]) -> None:
        super().__init__(message)
        self.suggestions = suggestions


@dataclass(frozen=True)
class Origin:
    origin_id: str
    ds_division: str
    district: str
    province: str


def _norm(text: str) -> str:
    return " ".join(text.casefold().replace("-", " ").replace(".", " ").split())


class TravelRepository:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        if not Path(db_path).is_file():
            raise FileNotFoundError(f"{db_path} not found; run `python -m travel_time_agent.build_db`")
        self.connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def _all(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute(sql, params)]

    # --- lookups ----------------------------------------------------------------
    def districts(self) -> list[dict[str, Any]]:
        return self._all(
            "SELECT d.district, d.province, count(o.origin_id) AS ds_divisions, "
            "(SELECT count(*) FROM campuses c WHERE c.district = d.district AND c.status = 'confirmed') "
            "AS campuses FROM districts d LEFT JOIN ds_divisions o USING (district) "
            "GROUP BY d.district ORDER BY d.district")

    def ds_divisions(self, district: str | None = None) -> list[Origin]:
        rows = self._all("SELECT origin_id, ds_division, district, province FROM ds_divisions "
                         "ORDER BY district, ds_division")
        if district:
            wanted = self._district(district)
            rows = [r for r in rows if r["district"] == wanted]
        return [Origin(**r) for r in rows]

    def _district(self, name: str) -> str:
        names = [r["district"] for r in self._all("SELECT district FROM districts")]
        exact = {_norm(n): n for n in names}
        if _norm(name) in exact:
            return exact[_norm(name)]
        close = difflib.get_close_matches(_norm(name), list(exact), n=3, cutoff=0.6)
        if len(close) == 1:
            return exact[close[0]]
        raise LookupError_(f"Unknown district {name!r}", [exact[c] for c in close])

    def find_origin(self, name: str, district: str | None = None) -> Origin:
        """Resolve a DS division (or the DS division named after a town)."""

        candidates = self.ds_divisions(district)
        by_name = {_norm(o.ds_division): o for o in candidates}
        key = _norm(name)
        if key in by_name:
            return by_name[key]
        partial = [o for k, o in by_name.items() if key in k.split() or k.startswith(key)]
        if len(partial) == 1:
            return partial[0]
        close = difflib.get_close_matches(key, list(by_name), n=5, cutoff=0.75)
        if len(close) == 1 and not partial:
            return by_name[close[0]]
        suggestions = [f"{o.ds_division} ({o.district})" for o in partial] or [
            f"{by_name[c].ds_division} ({by_name[c].district})" for c in close]
        raise LookupError_(f"No DS division matching {name!r}"
                           + (f" in {district}" if district else ""), suggestions)

    def university_names(self) -> list[str]:
        return [r["university"] for r in self._all("SELECT DISTINCT university FROM campuses ORDER BY 1")]

    def find_university(self, name: str) -> str:
        names = self.university_names()
        key = _norm(name)
        hits = [n for n in names if key in _norm(n)]
        if len(hits) == 1:
            return hits[0]
        close = difflib.get_close_matches(key, [_norm(n) for n in names], n=3, cutoff=0.6)
        matches = [n for n in names if _norm(n) in close]
        if len(matches) == 1 and not hits:
            return matches[0]
        raise LookupError_(f"University {name!r} is {'ambiguous' if hits else 'unknown'}",
                           hits or matches)

    # --- travel ---------------------------------------------------------------------
    def from_origin(self, origin: Origin, university: str | None = None, limit: int | None = None,
                    include_candidates: bool = False) -> list[dict[str, Any]]:
        sql = ("SELECT campus_id, university, campus_site, campus_district, status, "
               "approximate_location, institution_id, university_id, road_km, drive_min, bus_min_est, "
               "straight_km, same_district FROM travel_detail WHERE origin_id = ?")
        params: list[Any] = [origin.origin_id]
        if not include_candidates:
            sql += " AND status = 'confirmed'"
        if university:
            sql += " AND university = ?"
            params.append(self.find_university(university))
        sql += " ORDER BY drive_min, road_km"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self._all(sql, *params)

    def faculty_sites(self, origin: Origin, faculty: str, university: str | None = None,
                      limit: int | None = None) -> list[dict[str, Any]]:
        """Sites for a faculty, e.g. 'Engineering' or 'Faculty of Medicine', ranked by travel time.

        A site matches when its name contains the faculty word(s) ('Faculty of
        Engineering, Hapugala') or a course taught there does (Moratuwa's main
        campus teaches Engineering). Matching courses are listed per site.
        """

        words = [w for w in _norm(faculty).split() if w not in {"faculty", "of", "the", "and", "&"}]
        if not words:
            raise LookupError_(f"No faculty name in {faculty!r}", [])
        rows = self.from_origin(origin, university, None)
        courses: dict[str, list[str]] = {}
        for row in self._all("SELECT campus_id, uni_code, course_name FROM offering_sites ORDER BY uni_code"):
            if all(w in _norm(row["course_name"]) for w in words):
                courses.setdefault(row["campus_id"], []).append(f"{row['uni_code']} {row['course_name']}")
        hits = []
        for row in rows:
            named = all(w in _norm(row["campus_site"]) for w in words)
            if named or row["campus_id"] in courses:
                hits.append({**row, "named_faculty_site": named,
                             "matching_courses": courses.get(row["campus_id"], [])})
        return hits[:limit] if limit else hits

    def course_offerings(self, origin: Origin, course: str | None = None,
                         limit: int | None = None) -> list[dict[str, Any]]:
        """Offerings (UGC uni-codes) ranked by travel time to the site where each is taught."""

        sql = ("SELECT uni_code, course_code, course_name, offering_id, campus_id, university, "
               "campus_site, campus_district, approximate_location, site_needs_review, road_km, "
               "drive_min, bus_min_est, same_district FROM offering_travel WHERE origin_id = ?")
        params: list[Any] = [origin.origin_id]
        if course:
            sql += " AND (course_code = ? OR lower(course_name) LIKE ?)"
            params += [course.zfill(3) if course.isdigit() else course, f"%{course.casefold()}%"]
        sql += " ORDER BY drive_min, uni_code"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self._all(sql, *params)

    def setting(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def summary(self, origin: Origin) -> dict[str, Any]:
        """Nearest campus overall vs nearest in the home district (the border-district case)."""

        rows = self.from_origin(origin)
        nearest = rows[0] if rows else None
        home = next((r for r in rows if r["same_district"]), None)
        return {
            "origin": origin.__dict__,
            "nearest": nearest,
            "nearest_in_home_district": home,
            "nearest_is_outside_home_district": bool(nearest and not nearest["same_district"]),
            "minutes_saved_vs_home_district": (
                round(home["drive_min"] - nearest["drive_min"], 1)
                if nearest and home and not nearest["same_district"] else None),
        }

    def flags(self, campus_id: str | None = None) -> list[dict[str, Any]]:
        if campus_id:
            return self._all("SELECT * FROM quality_flags WHERE campus_id = ?", campus_id)
        return self._all("SELECT * FROM quality_flags")
