"""Ranking agent: turn the pipeline report into suggestion lists (20 each).

Each list is an ordering of the offerings (course at a university, i.e. UGC
uni-codes) the student can apply for. Different lists answer different
questions; none of them is an admission probability.

1. ``zscore``      — by last year's Z-score analysis: the band order
                      unlikely -> reach -> competitive -> strong (most
                      ambitious first, as in a UGC preference list), and
                      within each band the latest cut-off, highest first.
2. ``preference``  — by interest plus selectivity:
                      score = preference mark + 2.5 x latest cut-off,
                      highest first.
3. ``distance``    — order 2 made distance-aware, with the cut-off and the
                      distance weighted equally (default, mode "equal"):
                      score = order-2 score - D x (car - nearest) / (farthest - nearest)
                      where D = 2.5 x (highest - lowest cut-off) among the
                      student's options. So going from the nearest to the
                      farthest site costs exactly as many points as going from
                      the lowest to the highest cut-off gains.
                      Mode "fixed" is the earlier rule: - 2 x car minutes / 540.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from campusyamu.core import settings

DEFAULT_LIMIT = settings.get("ranking.suggestions", 20)
ZSCORE_BAND_ORDER = ["unlikely", "reach", "competitive", "strong"]
CUTOFF_WEIGHT = settings.get("ranking.cutoff_weight", 2.5)
DISTANCE_MODE = settings.get("ranking.distance_mode", "equal")  # "equal": distance spread = cut-off spread; "fixed": -2 x car / 540
DISTANCE_WEIGHT = settings.get("ranking.distance_weight", -2.0)  # fixed mode only
DISTANCE_SCALE_MIN = settings.get("ranking.distance_scale_min", 540)  # fixed mode only


def _entry(row: dict[str, Any], **extra: Any) -> dict[str, Any]:
    flags = []
    if row.get("aptitude_test"):
        flags.append("aptitude test")
    if row.get("status") == "check_ol":
        flags.append("O/L to confirm")
    return {
        "uni_code": row["uni_code"],
        "course_code": row.get("course_code"),
        "details_block": row.get("details_block"),
        "course_name": row.get("course_name"),
        "university": row.get("university"),
        "site": (row.get("site") or "").split(" (incl.")[0] or None,
        "band": row.get("band"),
        "latest_cutoff": row.get("latest_cutoff"),
        "latest_year": (row.get("latest_year") or "").replace("_", "/") or None,
        "expected_margin": row.get("expected_margin"),
        "preference_score": row.get("preference_score"),
        "car_min": row.get("car_min"),
        "flags": flags,
        **extra,
    }


def _car(row: dict[str, Any]) -> float:
    return row.get("car_min") if row.get("car_min") is not None else 1e9


def zscore_order(rows: Iterable[dict[str, Any]], limit: int | None = DEFAULT_LIMIT) -> dict[str, Any]:
    rows = list(rows)
    ranked = [r for r in rows if r.get("band") in ZSCORE_BAND_ORDER and r.get("latest_cutoff") is not None]
    ranked.sort(key=lambda r: (ZSCORE_BAND_ORDER.index(r["band"]), -r["latest_cutoff"], _car(r), r["uni_code"]))
    left_out = len(rows) - len(ranked)
    return {
        "id": "zscore",
        "title": "By Z-score analysis (unlikely → reach → competitive → strong; highest last-year cut-off first)",
        "total": len(ranked),
        "suggestions": [_entry(r, position=i) for i, r in enumerate(ranked[:limit], 1)],
        "notes": [f"{left_out} option(s) without a numeric cut-off are not ranked here"] if left_out else [],
    }


def preference_order(rows: Iterable[dict[str, Any]], limit: int | None = DEFAULT_LIMIT,
                     weight: float = CUTOFF_WEIGHT) -> dict[str, Any]:
    rows = list(rows)
    base = {"id": "preference",
            "title": f"By your interests (preference mark + {weight} × last-year cut-off, highest first)"}
    if not any(r.get("preference_score") is not None for r in rows):
        return {**base, "total": 0, "suggestions": [],
                "notes": ["no interests given (--prefer), so this list is empty"]}
    scored = []
    for r in rows:
        if r.get("preference_score") is None or r.get("latest_cutoff") is None:
            continue
        scored.append((round(r["preference_score"] + weight * r["latest_cutoff"], 2), r))
    scored.sort(key=lambda sr: (-sr[0], -sr[1]["latest_cutoff"], _car(sr[1]), sr[1]["uni_code"]))
    left_out = len(rows) - len(scored)
    return {
        **base,
        "cutoff_weight": weight,
        "total": len(scored),
        "suggestions": [_entry(r, position=i, combined_score=s) for i, (s, r) in enumerate(scored[:limit], 1)],
        "notes": [f"{left_out} option(s) without a numeric cut-off are not ranked here"] if left_out else [],
    }


def distance_parts(rows: Iterable[dict[str, Any]], weight: float = CUTOFF_WEIGHT, mode: str = DISTANCE_MODE,
                   distance_weight: float = DISTANCE_WEIGHT, scale_min: float = DISTANCE_SCALE_MIN,
                   ) -> tuple[list[tuple[dict[str, Any], dict[str, float]]], dict[str, Any], str]:
    """The order-3 score split into parts, for every row that can be scored.

    Returns ([(row, {"interest", "cutoff", "distance"})], settings, title); the
    score is the sum of the parts.
    """

    usable = [r for r in rows if r.get("preference_score") is not None
              and r.get("latest_cutoff") is not None and r.get("car_min") is not None]
    if mode == "equal":
        cutoffs = [r["latest_cutoff"] for r in usable] or [0.0]
        cars = [r["car_min"] for r in usable] or [0.0]
        car_lo, car_hi = min(cars), max(cars)
        points = weight * (max(cutoffs) - min(cutoffs))       # what the cut-off term spans
        extra = {"distance_points": round(points, 2), "nearest_car_min": car_lo, "farthest_car_min": car_hi,
                 "cutoff_range": [min(cutoffs), max(cutoffs)]}

        def penalty(car: float) -> float:
            return -points * (car - car_lo) / (car_hi - car_lo) if car_hi > car_lo else 0.0
        title = (f"By interests + distance, balanced (preference mark + {weight} × last-year cut-off "
                 f"− distance 0…{points:.2f}; nearest→farthest site weighs the same as lowest→highest cut-off)")
    elif mode == "fixed":
        extra = {"distance_weight": distance_weight, "distance_scale_min": scale_min}

        def penalty(car: float) -> float:
            return distance_weight * car / scale_min
        title = (f"By interests + distance (preference mark + {weight} × last-year cut-off "
                 f"{distance_weight:+g} × car min / {scale_min:g}, highest first)")
    else:
        raise ValueError(f"unknown distance mode {mode!r}")
    parts = [(r, {"interest": r["preference_score"], "cutoff": weight * r["latest_cutoff"],
                  "distance": penalty(r["car_min"])}) for r in usable]
    return parts, extra, title


def distance_order(rows: Iterable[dict[str, Any]], limit: int | None = DEFAULT_LIMIT,
                   weight: float = CUTOFF_WEIGHT, mode: str = DISTANCE_MODE,
                   distance_weight: float = DISTANCE_WEIGHT,
                   scale_min: float = DISTANCE_SCALE_MIN) -> dict[str, Any]:
    rows = list(rows)
    base = {"id": "distance", "mode": mode}
    if not any(r.get("preference_score") is not None for r in rows):
        return {**base, "title": "By interests + distance", "total": 0, "suggestions": [],
                "notes": ["no interests given (--prefer), so this list is empty"]}
    parts, extra, title = distance_parts(rows, weight, mode, distance_weight, scale_min)
    scored = [(round(sum(p.values()), 2), p, r) for r, p in parts]
    scored.sort(key=lambda sr: (-sr[0], _car(sr[2]), -sr[2]["latest_cutoff"], sr[2]["uni_code"]))
    left_out = len(rows) - len(scored)
    return {
        **base, "title": title, "cutoff_weight": weight, **extra,
        "total": len(scored),
        "suggestions": [_entry(r, position=i, combined_score=sc, distance_penalty=round(p["distance"], 2),
                               parts={k: round(v, 2) for k, v in p.items()})
                        for i, (sc, p, r) in enumerate(scored[:limit], 1)],
        "notes": [f"{left_out} option(s) without a numeric cut-off or travel time are not ranked here"]
        if left_out else [],
    }


ORDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "zscore": zscore_order,
    "preference": preference_order,
    "distance": distance_order,
}


def build_rankings(report: dict[str, Any], limit: int | None = DEFAULT_LIMIT) -> dict[str, Any]:
    """All suggestion lists for one pipeline report."""

    rows = [row for band in report["bands"].values() for row in band]
    return {name: order(rows, limit) for name, order in ORDERS.items()}
