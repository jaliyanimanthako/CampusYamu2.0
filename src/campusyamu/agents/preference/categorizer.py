"""Mark and group the courses a student can apply for by the student's ranked interests.

Every course gets, for each interest, a match mark (1..10, how close it is), a
mismatch mark (-1..-10, how far off it is) and their sum, the net mark
(-9..+9). A course belongs to an interest's group when its match mark is at
least ``min_mark``; a course close to several interests appears in each.

``preference_score`` is one overall fit number per course: its best net mark
over the interests, with later interests' positive marks counting a little
less (1st x1.0, 2nd x0.9, 3rd x0.8, ...). Taking the best means a course is not
penalised for being far from one interest when it fits another.

Nothing is hidden: courses below ``min_mark`` for every interest are listed
as "other"; those with a preference_score of ``POOR_FIT`` or lower are also
listed as a poor fit for every interest.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from campusyamu.core import settings

from .categories import CATEGORY_BY_ID, CourseTags
from .interpreter import Interpretation, Preference, baseline_mark, baseline_mismatch

DEFAULT_MIN_MARK = settings.get("preferences.min_mark", 5)
RANK_WEIGHTS = tuple(settings.get("preferences.rank_weights", (1.0, 0.9, 0.8, 0.7)))
LAST_WEIGHT = settings.get("preferences.last_weight", 0.6)
POOR_FIT = settings.get("preferences.poor_fit", -5)


def rank_weight(rank: int) -> float:
    return RANK_WEIGHTS[rank - 1] if rank <= len(RANK_WEIGHTS) else LAST_WEIGHT


def _marks(row: dict[str, Any], pref: Preference, tags: dict[str, CourseTags]) -> dict[str, Any]:
    code = row.get("course_code", "")
    tag = tags.get(code)
    mark = pref.marks.get(code) or (baseline_mark(tag, pref) if tag else 1)
    mismatch = pref.mismatches.get(code) or (baseline_mismatch(tag, pref) if tag else -10)
    return {"rank": pref.rank, "phrase": pref.phrase, "mark": mark, "mismatch": mismatch,
            "net": mark + mismatch}


def _weighted(m: dict[str, Any]) -> float:
    return m["net"] * rank_weight(m["rank"]) if m["net"] > 0 else m["net"]


def _compact(row: dict[str, Any], m: dict[str, Any], named: bool) -> dict[str, Any]:
    keep = ("uni_code", "course_code", "course_name", "university", "site", "car_min", "band",
            "expected_margin", "status", "aptitude_test")
    return {**{k: row.get(k) for k in keep}, "mark": m["mark"], "mismatch": m["mismatch"], "net": m["net"],
            "named_by_student": named}


def categorize(rows: Iterable[dict[str, Any]], interpretation: Interpretation,
               tags: dict[str, CourseTags],
               sort_key: Callable[[dict[str, Any]], Any] = lambda r: r.get("car_min") or 1e9,
               min_mark: int = DEFAULT_MIN_MARK) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (rows with category marks and preference marks, preference report)."""

    tagged = []
    for row in rows:
        tag = tags.get(row.get("course_code", ""))
        row = {**row, "categories": dict(tag.marks) if tag else None}
        marks = [_marks(row, p, tags) for p in interpretation.preferences]

        def key(m):
            return (_weighted(m), -m["rank"])
        best = max(marks, key=key, default=None)
        in_groups = [m for m in marks if m["mark"] >= min_mark]
        row["preference_marks"] = marks
        row["preference_score"] = round(_weighted(best), 1) if best else None
        # the interest this course fits best among the groups it is listed in
        row["preference_rank"] = max(in_groups, key=key)["rank"] if in_groups else None
        tagged.append(row)

    groups = []
    for i, pref in enumerate(interpretation.preferences):
        members = [(r["preference_marks"][i], r) for r in tagged]
        members = [(m, r) for m, r in members if m["mark"] >= min_mark]
        members.sort(key=lambda mr: (-mr[0]["net"], -mr[0]["mark"], sort_key(mr[1])))
        eligible_codes = {r["course_code"] for r in tagged}
        groups.append({
            "rank": pref.rank, "phrase": pref.phrase,
            "categories": [{"id": c, "name": CATEGORY_BY_ID[c].name} for c in pref.categories],
            "named_courses": [tags[c].name for c in pref.courses if c in tags],
            "named_but_not_open": [tags[c].name for c in pref.courses if c in tags and c not in eligible_codes],
            "count": len(members),
            "rows": [_compact(r, m, r.get("course_code") in pref.courses) for m, r in members],
        })

    other = sorted((r for r in tagged if r["preference_rank"] is None),
                   key=lambda r: (-(r["preference_score"] or 0), sort_key(r)))
    best_overall = sorted((r for r in tagged if r["preference_rank"] is not None),
                          key=lambda r: (-r["preference_score"], sort_key(r)))
    poor = sorted((r for r in other if r["preference_score"] is not None and r["preference_score"] <= POOR_FIT),
                  key=lambda r: (r["preference_score"], sort_key(r)))
    report = {**interpretation.to_dict(), "min_mark": min_mark, "groups": groups,
              "best_overall": [{**{k: r.get(k) for k in ("uni_code", "course_name", "university", "band",
                                                        "car_min", "expected_margin")},
                                "preference_score": r["preference_score"],
                                "best_for": r["preference_rank"]} for r in best_overall],
              "other": {"count": len(other), "rows": [{k: r.get(k) for k in
                        ("uni_code", "course_name", "university", "band", "car_min", "preference_score")}
                        for r in other]},
              "poor_fit": {"threshold": POOR_FIT, "count": len(poor),
                           "rows": [{k: r.get(k) for k in ("uni_code", "course_name", "university",
                                                           "preference_score")} for r in poor]}}
    for pref in report["preferences"]:          # marks are on the rows; keep the summary readable
        pref.pop("marks", None)
        pref.pop("mismatches", None)
    return tagged, report
