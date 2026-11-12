"""Student pipeline (LangGraph): eligible courses, then Z-score analysis per course.

    uv run python -m student_pipeline --stream "Physical Science" \\
        --al "Combined Mathematics:A" --al "Physics:B" --al "Chemistry:C" --cgt 40 \\
        --admission-district Gampaha --home Minuwangoda \\
        --ol Science:B --ol English:B --ol Maths:A --z-score 1.56

    uv run python -m student_pipeline            # asks the questions
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from course_finder.cli import interactive_profile
from course_finder.finder import CourseFinder

from .graph import BAND_ORDER, build_pipeline, run_pipeline

BAND_TITLES = {
    "strong": "Strong (Z-score at or above recent cut-offs)",
    "competitive": "Competitive (close to the cut-off)",
    "reach": "Reach (below the estimated cut-off)",
    "unlikely": "Unlikely (well below recent cut-offs)",
    "no_history": "No cut-off history found",
}


def _time(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    h, m = divmod(round(minutes), 60)
    return f"{h}h{m:02d}" if h else f"{m}m"


def _line(row: dict[str, Any]) -> str:
    where = f"{row.get('university') or '?'} — {(row.get('site') or '?').split(' (incl.')[0]}"
    head = f"  {row['uni_code']:<5} {row['course_name']} | {where} | car {_time(row.get('car_min'))}"
    flags = []
    if row.get("aptitude_test"):
        flags.append("aptitude test")
    if row.get("status") == "check_ol":
        flags.append("O/L to confirm")
    if row.get("matched_by") == "name_variant":
        flags.append(f"cut-offs listed as '{row['zscore_series'].split(' — ', 1)[1]}'")
    if "predicted_cutoff" not in row:
        return head + f"\n        {row.get('zscore_note') or 'no cut-off history'}" + (
            f"  ({', '.join(flags)})" if flags else "")
    year = row["latest_year"].replace("_", "/")
    return (head + f"\n        est. cut-off {row['predicted_cutoff']:.4f} ± {row['uncertainty']:.4f}"
            f" | latest {row['latest_cutoff']:.4f} ({year}) | your margin {row['expected_margin']:+.4f}"
            f" | met {row['years_met']}/{row['years_compared']} years | evidence {row['evidence_confidence']}"
            + (f"  ({', '.join(flags)})" if flags else ""))


def render(state: dict[str, Any], limit: int | None, sort: str = "travel") -> str:
    report = state["report"]
    p, o = report["profile"], report["origin"]
    al = ", ".join(f"{s} {g}" for s, g in p["al_results"])
    counts = report["counts"]
    lines = [
        f"Student: {p['stream']} — {al}; CGT {p['common_general_test']}; Z-score {p.get('z_score')}",
        f"Admission district: {p['admission_district']} | Home: {o['ds_division']} ({o['district']})",
        f"Step 1 (KG): {counts['can_apply']} courses open, {counts['with_conditions']} with conditions, "
        f"{counts['blocked_by_ol']} blocked by O/L, {counts['not_eligible']} not eligible by A/L",
        "Step 2 (Z-score): " + ", ".join(f"{counts['band_' + b]} {b.replace('_', ' ')}" for b in BAND_ORDER),
    ]
    for band in BAND_ORDER:
        rows = report["bands"][band]
        if sort == "margin":
            rows = sorted(rows, key=lambda r: -(r.get("expected_margin") if r.get("expected_margin") is not None else -9))
        if not rows:
            continue
        shown = rows if limit is None else rows[:limit]
        lines += ["", f"== {BAND_TITLES[band]} ({len(rows)}) =="] + [_line(r) for r in shown]
        if len(shown) < len(rows):
            lines.append(f"  … {len(rows) - len(shown)} more (use --all)")
    lines += [""] + [f"Note: {n}" for n in report["notes"]]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stream")
    parser.add_argument("--al", action="append", default=[])
    parser.add_argument("--cgt", type=int, default=30)
    parser.add_argument("--admission-district", "--district", dest="admission_district")
    parser.add_argument("--home")
    parser.add_argument("--ol", action="append", default=[])
    parser.add_argument("--z-score", type=float)
    parser.add_argument("--limit", type=int, default=10, help="Rows per band (default 10)")
    parser.add_argument("--all", action="store_true", help="Show every row")
    parser.add_argument("--sort", choices=["travel", "margin"], default="travel",
                        help="Order within each band: nearest first (default) or largest Z-score margin")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args(argv)

    finder = CourseFinder()
    try:
        if args.stream or args.al:
            inputs = dict(stream=args.stream, al=args.al, cgt=args.cgt,
                          admission_district=args.admission_district, home=args.home,
                          ol=args.ol, z_score=args.z_score)
            if None in (args.stream, args.admission_district, args.home) or len(args.al) != 3:
                parser.error("give --stream, three --al, --admission-district and --home "
                             "(or no flags for questions)")
        else:
            if not sys.stdin.isatty():
                parser.error("no student details given; pass flags or run in a terminal for questions")
            profile = interactive_profile(finder)
            inputs = dict(stream=profile.stream, al=[f"{s}:{g}" for s, g in profile.al_results],
                          cgt=profile.common_general_test, admission_district=profile.admission_district,
                          home=profile.home, ol=[f"{s}:{g}" for s, g in profile.ol_results.items()],
                          z_score=profile.z_score)
            print()
        state = run_pipeline(inputs, build_pipeline(finder))
    finally:
        finder.close()

    if state.get("errors"):
        parser.exit(1, "Input problem: " + "; ".join(state["errors"]) + "\n")
    if args.save:
        args.save.write_text(json.dumps(state["report"], ensure_ascii=False, indent=1, default=str),
                             encoding="utf-8")
    if args.json:
        print(json.dumps(state["report"], ensure_ascii=False, indent=1, default=str))
    else:
        print(render(state, None if args.all else args.limit, args.sort))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
