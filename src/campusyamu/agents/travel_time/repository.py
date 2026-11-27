"""Read-only queries over ``data/processed/travel/travel_times.db``."""

from __future__ import annotations

import difflib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_db import DEFAULT_DB


class LookupError_(LookupError):
    """A town / university that cannot be resolved, with suggestions."""

    def __init__(self, message: str, suggestions: list[str]) -> None:
        super().__init__(message)
        self.suggestions = suggestions


@dataclass(frozen=True)
class Origin:
    """A home town: where travel times are measured from."""

    origin_id: str
    town: str
    district: str
    province: str

    @property
    def label(self) -> str:
        return f"{self.town} ({self.district})"


# which town stands in for a whole DS division (old saved forms sent a DS division)
SOURCE_RANK = {"osm_city": 0, "osm_town": 1, "manual": 2}
DISTRICT_SUFFIX_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")


def _edits(a: str, b: str) -> int:
    """Levenshtein distance."""

    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, start=1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def _same_start(key: str, options: list[str]) -> list[str]:
    """Options a typo could plausibly have come from: same first letter, and one edit away
    (two for names over 10 letters). Without this, 'Peradeniya' (not a listed town) would
    'fix' to 'Hedeniya' or 'Padeniya', a different place."""

    limit = 1 if len(key) <= 10 else 2
    return [o for o in options if o[:1] == key[:1] and _edits(key, o) <= limit]


def _best_match(key: str, options: list[str]) -> str | None:
    """A clear typo fix: the closest option when it is close and well ahead of the next one."""

    scored = sorted(((difflib.SequenceMatcher(None, key, o).ratio(), o) for o in _same_start(key, options)),
                    reverse=True)
    if not scored:
        return None
    top = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return top[1] if top[0] >= 0.85 and top[0] - runner_up >= 0.1 else None


def _norm(text: str) -> str:
    return " ".join(text.casefold().replace("-", " ").replace(".", " ").split())


class TravelRepository:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        if not Path(db_path).is_file():
            raise FileNotFoundError(f"{db_path} not found; run `python -m campusyamu.agents.travel_time.build_db`")
        self.connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def _all(self, sql: str, *params: Any) -> list[dict[str, Any]]:
        return [dict(r) for r in self.connection.execute(sql, params)]

    # --- lookups ----------------------------------------------------------------
    def districts(self) -> list[dict[str, Any]]:
        return self._all(
            "SELECT d.district, d.province, count(o.origin_id) AS towns, "
            "(SELECT count(*) FROM campuses c WHERE c.district = d.district AND c.status = 'confirmed') "
            "AS campuses FROM districts d LEFT JOIN towns o USING (district) "
            "GROUP BY d.district ORDER BY d.district")

    def towns(self, district: str | None = None) -> list[Origin]:
        rows = self._all("SELECT origin_id, town, district, province FROM towns ORDER BY district, town")
        if district:
            wanted = self._district(district)
            rows = [r for r in rows if r["district"] == wanted]
        return [Origin(**r) for r in rows]

    def town_for_ds_division(self, ds_division: str, district: str | None = None) -> Origin | None:
        """The main town of a DS division: the town named after it, else its biggest place."""

        rows = self._all("SELECT origin_id, town, district, province, ds_division, point_source FROM towns")
        key = _norm(ds_division)
        rows = [r for r in rows if _norm(r["ds_division"]) == key]
        if district:
            wanted = self._district(district)
            rows = [r for r in rows if r["district"] == wanted]
        if not rows:
            return None
        best = min(rows, key=lambda r: (_norm(r["town"]) != key, SOURCE_RANK.get(r["point_source"], 3), r["town"]))
        return Origin(best["origin_id"], best["town"], best["district"], best["province"])

    def _district(self, name: str) -> str:
        names = [r["district"] for r in self._all("SELECT district FROM districts")]
        exact = {_norm(n): n for n in names}
        if _norm(name) in exact:
            return exact[_norm(name)]
        best = _best_match(_norm(name), list(exact))
        if best:
            return exact[best]
        close = difflib.get_close_matches(_norm(name), list(exact), n=3, cutoff=0.6)
        raise LookupError_(f"Unknown district {name!r}", [exact[c] for c in close])

    def find_origin(self, name: str, district: str | None = None) -> Origin:
        """Resolve a home town: 'Kotugoda', 'Hettipola (Matale)', a typo, or an old DS division name.

        A few town names exist in two districts; without a district those are
        ambiguous and the error lists both.
        """

        match = DISTRICT_SUFFIX_RE.match(name.strip())
        if match and not district:
            try:
                district = self._district(match.group(2))
                name = match.group(1)
            except LookupError_:
                pass                              # '(...)' is part of the name, not a district
        candidates = self.towns(district)
        by_name: dict[str, list[Origin]] = {}
        for o in candidates:
            by_name.setdefault(_norm(o.town), []).append(o)
        key = _norm(name)

        def one(found: list[Origin]) -> Origin:
            if len(found) == 1:
                return found[0]
            raise LookupError_(f"Town {name!r} is in more than one district; give the district",
                               [o.label for o in found])

        if key in by_name:
            return one(by_name[key])
        legacy = self.town_for_ds_division(name, district)
        if legacy:
            return legacy
        partial = [o for k, os in by_name.items() if key in k.split() or k.startswith(key) for o in os]
        if len(partial) == 1:
            return partial[0]
        best = None if partial else _best_match(key, list(by_name))
        if best:
            return one(by_name[best])
        close = difflib.get_close_matches(key, list(by_name), n=5, cutoff=0.75)
        same_start = _same_start(key, close)
        if len(same_start) == 1 and not partial:
            return one(by_name[same_start[0]])
        suggestions = [o.label for o in partial] or [o.label for c in close for o in by_name[c]]
        raise LookupError_(f"No town matching {name!r}" + (f" in {district}" if district else ""),
                           suggestions)

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
