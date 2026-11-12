"""What-if analysis for order 3: how each course moves if the student leans on one factor.

The balanced order-3 score is interest + cut-off + distance. Each profile
re-weights those parts (x1.5 on one of them) and re-ranks every option, so we
can say "this course rises to #3 if being close to home matters more".

Everything here is computed; the LLM (feedback.py) only explains these facts.
"""

from __future__ import annotations

from statistics import fmean
from typing import Any, Iterable

from .ranking import CUTOFF_WEIGHT, DEFAULT_LIMIT, DISTANCE_MODE, distance_parts

NUDGE = 1.5
PROFILES: dict[str, dict[str, float]] = {
    "balanced": {"interest": 1.0, "cutoff": 1.0, "distance": 1.0},
    "closer_to_home": {"interest": 1.0, "cutoff": 1.0, "distance": NUDGE},
    "interest_first": {"interest": NUDGE, "cutoff": 1.0, "distance": 1.0},
    "selectivity_first": {"interest": 1.0, "cutoff": NUDGE, "distance": 1.0},
}
PROFILE_LABELS = {
    "balanced": "considering everything equally",
    "closer_to_home": "if being close to home matters more",
    "interest_first": "if studying what you like matters more",
    "selectivity_first": "if a high-demand (high cut-off) course matters more",
}
PART_LABELS = {
    "interest": "fits your interests",
    "cutoff": "high-demand course (high cut-off)",
    "distance": "close to home",
}
NOTABLE_MOVE = 3            # places
SAFE_TOP = 10               # "stays in your top 10 whatever you prioritise"
CLOSE_GAP = 0.15            # score points between neighbours


def _ranks(parts: list[tuple[dict[str, Any], dict[str, float]]], weights: dict[str, float]) -> dict[str, tuple[int, float]]:
    scored = [(sum(weights[k] * v for k, v in p.items()), r) for r, p in parts]
    scored.sort(key=lambda sr: (-sr[0], sr[1]["car_min"], -sr[1]["latest_cutoff"], sr[1]["uni_code"]))
    return {r["uni_code"]: (i, round(score, 2)) for i, (score, r) in enumerate(scored, 1)}


def analyse(rows: Iterable[dict[str, Any]], limit: int | None = DEFAULT_LIMIT, weight: float = CUTOFF_WEIGHT,
            mode: str = DISTANCE_MODE) -> dict[str, Any]:
    rows = list(rows)
    parts, _, _ = distance_parts(rows, weight, mode)
    if not parts:
        return {"profiles": PROFILES, "courses": [], "close_calls": [], "risers": {}}
    top = limit or len(parts)
    ranks = {name: _ranks(parts, w) for name, w in PROFILES.items()}
    by_code = {r["uni_code"]: (r, p) for r, p in parts}
    listed = sorted(by_code, key=lambda c: ranks["balanced"][c][0])[:top]
    # strength / weakness = the part where a course is most above / below the other listed courses
    means = {k: fmean(by_code[c][1][k] for c in listed) for k in ("interest", "cutoff", "distance")}

    def facts(code: str) -> dict[str, Any]:
        row, p = by_code[code]
        deviation = {k: p[k] - means[k] for k in p}
        strength = max(deviation, key=deviation.get)
        weakness = min(deviation, key=deviation.get)
        balanced = ranks["balanced"][code][0]
        profile_ranks = {name: ranks[name][code][0] for name in PROFILES if name != "balanced"}
        return {
            "uni_code": code, "course_name": row.get("course_name"), "university": row.get("university"),
            "band": row.get("band"), "expected_margin": row.get("expected_margin"),
            "latest_cutoff": row.get("latest_cutoff"), "car_min": row.get("car_min"),
            "aptitude_test": bool(row.get("aptitude_test")), "ol_to_confirm": row.get("status") == "check_ol",
            "parts": {k: round(v, 2) for k, v in p.items()}, "score": ranks["balanced"][code][1],
            "balanced_rank": balanced, "in_list": balanced <= top,
            "profile_ranks": profile_ranks,
            "moves": {name: balanced - r for name, r in profile_ranks.items()},      # + = moves up
            "worst_rank": max([balanced, *profile_ranks.values()]),
            "strength": strength, "weakness": weakness if deviation[weakness] < 0 else None,
        }

    risers = {name: sorted((c for c in by_code if ranks[name][c][0] <= top and c not in listed),
                           key=lambda c: ranks[name][c][0])
              for name in PROFILES if name != "balanced"}
    extra = sorted({c for codes in risers.values() for c in codes}, key=lambda c: ranks["balanced"][c][0])
    courses = [facts(c) for c in listed + extra]
    # near ties: runs of neighbours whose scores differ by less than CLOSE_GAP each
    close_calls, run = [], listed[:1]
    for a, b in zip(listed, listed[1:]):
        if ranks["balanced"][a][1] - ranks["balanced"][b][1] < CLOSE_GAP:
            run.append(b)
            continue
        if len(run) > 1:
            close_calls.append(run)
        run = [b]
    if len(run) > 1:
        close_calls.append(run)
    close_calls = [{"uni_codes": codes, "ranks": [ranks["balanced"][codes[0]][0], ranks["balanced"][codes[-1]][0]],
                    "spread": round(ranks["balanced"][codes[0]][1] - ranks["balanced"][codes[-1]][1], 2)}
                   for codes in close_calls]
    return {
        "profiles": PROFILES, "profile_labels": PROFILE_LABELS, "part_labels": PART_LABELS,
        "thresholds": {"notable_move": NOTABLE_MOVE, "safe_top": SAFE_TOP, "close_gap": CLOSE_GAP,
                       "list_size": top, "options_ranked": len(parts)},
        "courses": courses,
        "safe_picks": [c["uni_code"] for c in courses if c["in_list"] and c["worst_rank"] <= SAFE_TOP],
        "risers": risers,                     # outside the list, but in it under that profile
        "close_calls": close_calls,
    }
