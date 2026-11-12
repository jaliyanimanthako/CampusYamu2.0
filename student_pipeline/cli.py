"""Student pipeline (LangGraph): eligible courses, then Z-score analysis per course.

    uv run python -m student_pipeline --stream "Physical Science" \\
        --al "Combined Mathematics:A" --al "Physics:B" --al "Chemistry:C" --cgt 40 \\
        --admission-district Gampaha --home Minuwangoda \\
        --ol Science:B --ol English:B --ol Maths:A --z-score 1.56 \\
        --prefer "engineering, design, planning"

    uv run python -m student_pipeline            # asks the questions

--prefer is free text (first = most liked). It is read by one small OpenAI call
(OPENAI_API_KEY from .env; model PREFERENCE_MODEL, else OPENAI_MODEL, else
gpt-4o-mini). Without a key, or with --no-llm, keyword matching is used.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from course_finder.cli import interactive_profile
from course_finder.finder import CourseFinder
from RAG_Agent.graph_pipeline.handbook_prose import _load_env

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


def render_preferences(prefs: dict[str, Any], limit: int | None) -> list[str]:
    if prefs.get("method") == "none" and not prefs.get("notes"):
        return []
    how = {"llm": f"LLM ({prefs.get('model')})", "keywords": "keyword matching + reviewed course marks",
           "none": "—"}[prefs["method"]]
    lines = ["", f"Your interests: \"{prefs['text']}\"  → marked by {how}",
             f"Per interest each course gets a match mark (1..10), a mismatch mark (-1..-10) and net = sum; "
             f"listed when the match mark is {prefs['min_mark']}+"]
    if prefs.get("best_overall"):
        lines += ["", "== Best fit overall (all your interests) =="]
        shown = prefs["best_overall"] if limit is None else prefs["best_overall"][:limit]
        for r in shown:
            margin = f" | margin {r['expected_margin']:+.4f}" if r.get("expected_margin") is not None else ""
            lines.append(f"  {r['preference_score']:>+5.1f}  {r['band'].replace('_', ' '):<11} {r['uni_code']:<5} "
                         f"{r['course_name']} | {r.get('university') or '?'} | car {_time(r.get('car_min'))}"
                         f"{margin}  (best for #{r['best_for']})")
        if len(shown) < len(prefs["best_overall"]):
            lines.append(f"  … {len(prefs['best_overall']) - len(shown)} more (use --all)")
    for group in prefs["groups"]:
        cats = " + ".join(c["name"] for c in group["categories"])
        lines += ["", f"== Interest {group['rank']}: {group['phrase']} → {cats} ({group['count']}) =="]
        for name in group["named_but_not_open"]:
            lines.append(f"  ! {name}: you named it, but it is not open to you (A/L subjects or O/L)")
        shown = group["rows"] if limit is None else group["rows"][:limit]
        for r in shown:
            margin = f" | margin {r['expected_margin']:+.4f}" if r.get("expected_margin") is not None else ""
            where = (r.get("site") or "?").split(" (incl.")[0]
            lines.append(f"  {r['mark']:>2} {r['mismatch']:>3} = {r['net']:>+3}  "
                         f"{r['band'].replace('_', ' '):<11} {r['uni_code']:<5} "
                         f"{r['course_name']} | {r.get('university') or '?'} — {where} | "
                         f"car {_time(r.get('car_min'))}{margin}" + ("  (you named it)" if r["named_by_student"] else ""))
        if len(shown) < len(group["rows"]):
            lines.append(f"  … {len(group['rows']) - len(shown)} more (use --all)")
        if not group["rows"]:
            lines.append("  (none of the courses you can apply for is close to this interest)")
    if prefs["unmatched"]:
        lines.append(f"\nNot understood: {', '.join(prefs['unmatched'])}")
    lines += [f"Note: {n}" for n in prefs.get("notes", [])]
    if prefs["groups"]:
        lines.append(f"Other courses you can apply for (below {prefs['min_mark']}/10 for every interest): "
                     f"{prefs['other']['count']} — all are listed by Z-score band below")
        poor = prefs.get("poor_fit") or {}
        if poor.get("rows"):
            names = ", ".join(f"{r['uni_code']} {r['course_name']} ({r['preference_score']:+.0f})"
                              for r in poor["rows"][:8])
            lines.append(f"Far from all your interests (net {poor['threshold']} or lower): {poor['count']} — "
                         f"{names}" + (" …" if poor["count"] > 8 else ""))
    return lines


def render_rankings(rankings: dict[str, Any]) -> list[str]:
    lines = []
    for number, ranking in enumerate(rankings.values(), 1):
        shown = len(ranking["suggestions"])
        lines += ["", f"== Order {number}: {ranking['title']} — top {shown} of {ranking['total']} =="]
        for s in ranking["suggestions"]:
            cutoff = (f"cut-off {s['latest_cutoff']:.4f} ({s['latest_year']})"
                      if s.get("latest_cutoff") is not None else "no cut-off")
            margin = f" | margin {s['expected_margin']:+.4f}" if s.get("expected_margin") is not None else ""
            score = ""
            if "combined_score" in s:
                score = (f"{s['combined_score']:>6.2f} = {s['preference_score']:+.1f} + "
                         f"{ranking['cutoff_weight']}×{s['latest_cutoff']:.4f}"
                         + (f" {s['distance_penalty']:+.2f}" if "distance_penalty" in s else "") + "  ")
            where = f"{s.get('university') or '?'} — {s.get('site') or '?'}"
            lines.append(f"  {s['position']:>2}. {score}{s['band'].replace('_', ' '):<11} {s['uni_code']:<5} "
                         f"{s['course_name']} | {where} | {cutoff}{margin} | car {_time(s.get('car_min'))}"
                         + (f"  ({', '.join(s['flags'])})" if s["flags"] else ""))
            lines += _what_if_lines(ranking, s["uni_code"])
        lines += [f"  Note: {n}" for n in ranking["notes"]]
        lines += render_feedback(ranking)
    return lines


WHAT_IF_SHORT = {"closer_to_home": "closer to home", "interest_first": "interest first",
                 "selectivity_first": "selectivity first"}


def _what_if_lines(ranking: dict[str, Any], code: str) -> list[str]:
    analysis, feedback = ranking.get("analysis"), ranking.get("feedback")
    if not analysis:
        return []
    facts = next((c for c in analysis["courses"] if c["uni_code"] == code), None)
    lines = []
    if facts:
        ranks = " · ".join(f"{WHAT_IF_SHORT[p]} #{r}" for p, r in facts["profile_ranks"].items())
        lines.append(f"        what-if: {ranks}")
    note = ((feedback or {}).get("course_notes") or {}).get(code)
    if note:
        lines.append(f"        ↳ {note['note']}")
    return lines


def render_feedback(ranking: dict[str, Any]) -> list[str]:
    feedback, analysis = ranking.get("feedback"), ranking.get("analysis") or {}
    if not feedback or feedback.get("method") == "none":
        return []
    how = f"LLM ({feedback.get('model')})" if feedback["method"] == "llm" else "template sentences"
    lines = ["", f"  -- Feedback on order 3 (written by {how}; ranks and numbers are computed) --",
             f"  {feedback['summary']}"]
    risers = [c for c in analysis.get("courses", []) if not c["in_list"]]
    if risers:
        lines.append("  Outside the list, but rise into it under a what-if:")
        for c in risers:
            note = feedback["course_notes"].get(c["uni_code"], {}).get("note", "")
            lines.append(f"    {c['uni_code']:<5} {c['course_name']} | {c['university']} — {note}")
    for p in feedback["priorities"]:
        lines.append(f"  • {p['label'][0].upper() + p['label'][1:]}: {p['advice']}")
    for cc in feedback["close_calls"]:
        lines.append(f"  • Close call: {cc['note']}")
    lines += [f"  ! {c}" for c in feedback["cautions"]]
    lines += [f"  Note: {n}" for n in feedback.get("notes", [])]
    return lines


def render(state: dict[str, Any], limit: int | None, sort: str = "travel", view: str = "all") -> str:
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
    if view in ("all", "rankings"):
        lines += render_rankings(report.get("rankings") or {})
    if view == "rankings":
        return "\n".join(lines)
    lines += render_preferences(report.get("preferences") or {"method": "none"}, limit)
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
    parser.add_argument("--prefer", action="append", default=[],
                        help="What the student likes to study, free text (repeatable; first = most liked)")
    parser.add_argument("--no-llm", action="store_true", help="Read --prefer with keyword matching only")
    parser.add_argument("--min-mark", type=int, default=5, choices=range(1, 11), metavar="1-10",
                        help="List a course under an interest when its mark is at least this (default 5)")
    parser.add_argument("--env-file", type=Path, help="Load OPENAI_API_KEY etc. from this file (default ./.env)")
    parser.add_argument("--limit", type=int, default=10, help="Rows per band (default 10)")
    parser.add_argument("--all", action="store_true", help="Show every row")
    parser.add_argument("--sort", choices=["travel", "margin"], default="travel",
                        help="Order within each band: nearest first (default) or largest Z-score margin")
    parser.add_argument("--view", choices=["all", "rankings", "details"], default="all",
                        help="rankings = only the suggestion lists; details = interests and bands without them")
    parser.add_argument("--suggestions", type=int, default=20, help="Entries per suggestion list (default 20)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args(argv)
    try:
        _load_env(args.env_file)
    except Exception as exc:                       # a bad .env should not stop an offline run
        print(f"warning: could not load env file: {exc}", file=sys.stderr)

    finder = CourseFinder()
    try:
        if args.stream or args.al:
            inputs = dict(stream=args.stream, al=args.al, cgt=args.cgt,
                          admission_district=args.admission_district, home=args.home,
                          ol=args.ol, z_score=args.z_score, preferences=", ".join(args.prefer))
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
                          z_score=profile.z_score,
                          preferences=", ".join(args.prefer) or input(
                              "What would you like to study? e.g. engineering, design, maths "
                              "(first = most liked; Enter to skip): ").strip())
            print()
        state = run_pipeline(inputs, build_pipeline(finder, use_llm=not args.no_llm, min_mark=args.min_mark,
                                                   suggestions=args.suggestions))
    finally:
        finder.close()

    if state.get("errors"):
        parser.exit(1, "Input problem: " + "; ".join(state["errors"]) + "\n")
    if args.save:
        args.save.write_text(json.dumps(state["report"], ensure_ascii=False, indent=1, default=str),
                             encoding="utf-8")
        print(f"Saved full report to {args.save}", file=sys.stderr)
    if args.json:
        print(json.dumps(state["report"], ensure_ascii=False, indent=1, default=str))
    else:
        print(render(state, None if args.all else args.limit, args.sort, args.view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
