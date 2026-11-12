"""Find the courses a student can apply for (pipeline step 1).

With flags:
    uv run python -m course_finder \\
        --stream "Physical Science" \\
        --al "Combined Mathematics:A" --al "Physics:B" --al "Chemistry:C" \\
        --cgt 40 --admission-district Gampaha --home Minuwangoda \\
        --ol Science:B --ol English:B --ol Maths:A --z-score 1.56

Interactively (asks each question, re-asks on a typo):
    uv run python -m course_finder
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Sequence

from .finder import (APTITUDE, BLOCKED_OL, CHECK_OL, DEFAULT_GRAPH, CourseFinder, CourseMatch,
                     FinderResult, ProfileError, StudentProfile)
from travel_time_agent.build_db import DEFAULT_DB

GROUP_TITLES = {
    "can_apply": "You can apply",
    "with_conditions": "You can apply, with extra conditions",
    "check_handbook": "Check the handbook (rule text not fully resolved)",
    "blocked_by_ol": "Not open: O/L requirement not met",
}
MARKS = {APTITUDE: "aptitude test", CHECK_OL: "to confirm", BLOCKED_OL: "O/L not met"}


def _time(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    h, m = divmod(round(minutes), 60)
    return f"{h}h{m:02d}" if h else f"{m}m"


def _offering_line(o) -> str:
    where = f"{o.university or '?'} — {o.site or '?'}"
    marks = []
    if o.status in MARKS:
        detail = {CHECK_OL: o.ol_unknown, BLOCKED_OL: o.ol_failed}.get(o.status)
        marks.append(MARKS[o.status] + (f": {'; '.join(detail)}" if detail else ""))
    elif o.aptitude_test:
        marks.append("aptitude test")
    if o.same_district:
        marks.append("near home: same district")
    if o.site_to_confirm:
        marks.append("teaching site to confirm")
    if o.approximate_location:
        marks.append("approx. location")
    return (f"      {o.uni_code:<5} car {_time(o.car_min):>5} | bus ≈ {_time(o.bus_min_est):>5}  {where}"
            + (f"  ({', '.join(marks)})" if marks else ""))


def _course_block(course: CourseMatch, max_car: float | None) -> list[str]:
    offerings = [o for o in course.offerings if max_car is None or (o.car_min or 1e9) <= max_car]
    if not offerings:
        return []
    lines = [f"  {course.course_code} {course.name}"]
    lines += [_offering_line(o) for o in offerings]
    for text in course.additional_conditions:
        lines.append(f"      + condition: {text}")
    for text in course.programmes_not_open:
        lines.append(f"      ! not open to you: {text}")
    for text in course.unresolved_text[:2]:
        lines.append(f"      ? handbook: {' '.join(text.split())[:160]}")
    return lines


def render(result: FinderResult, max_car: float | None = None, show_not_eligible: bool = False) -> str:
    p, o = result.profile, result.origin
    al = ", ".join(f"{s} {g}" for s, g in p["al_results"])
    ol = ", ".join(f"{s} {g}" for s, g in p["ol_results"].items())
    groups = result.by_group()
    lines = [
        f"Student: {p['stream']} — {al}; CGT {p['common_general_test']}",
        f"O/L: {ol}",
        f"Admission district: {p['admission_district']} (§1.5; for Z-score cut-offs in the next step)"
        + (f" | Z-score {p['z_score']} (not used in this step)" if p.get("z_score") is not None else ""),
        f"Home: {o['ds_division']} DS division, {o['district']} district (used for travel times)",
        "",
        f"Summary: {len(groups['can_apply'])} can apply · {len(groups['with_conditions'])} with conditions · "
        f"{len(groups['check_handbook'])} check handbook · {len(groups['blocked_by_ol'])} blocked by O/L · "
        f"{len(groups['not_eligible'])} not eligible by A/L subjects",
    ]
    if max_car is not None:
        lines.append(f"(showing offerings within {_time(max_car)} by car)")
    for key, title in GROUP_TITLES.items():
        blocks = [b for c in groups[key] if (b := _course_block(c, max_car))]
        if not blocks:
            continue
        lines += ["", f"== {title} ({len(blocks)}) =="]
        for block in blocks:
            lines += block
    if show_not_eligible and groups["not_eligible"]:
        lines += ["", f"== Not eligible by A/L subjects ({len(groups['not_eligible'])}) =="]
        for course in groups["not_eligible"]:
            lines.append(f"  {course.course_code} {course.name}")
            lines += [f"      - {r}" for r in course.reasons[:2]]
    lines += [""] + [f"Note: {n}" for n in result.notes]
    return "\n".join(lines)


# --- interactive input -------------------------------------------------------------
def _ask(prompt: str, convert: Callable[[str], object], default: str | None = None,
         reader: Callable[[str], str] = input):
    while True:
        raw = reader(f"{prompt}{f' [{default}]' if default else ''}: ").strip() or (default or "")
        try:
            return convert(raw)
        except (ProfileError, ValueError) as exc:
            hint = getattr(exc, "suggestions", None)
            print(f"  ! {exc}" + (f" — did you mean: {', '.join(hint[:6])}?" if hint else ""))


def interactive_profile(finder: CourseFinder, reader: Callable[[str], str] = input) -> StudentProfile:
    print("Answer each question (Enter keeps the [default]).\n")

    def need(text: str) -> str:
        if not text:
            raise ValueError("this answer is required")
        return text

    def al(text: str) -> list[str]:
        items = [i for i in (part.strip() for part in text.split(",")) if i]
        if len(items) != 3:
            raise ValueError("give three subjects with grades, e.g. Combined Mathematics A, Physics B, Chemistry C")
        StudentProfile.from_inputs(stream="x", al=items, cgt=30, admission_district="x", home="x", ol=[])
        return items

    def ol(text: str) -> list[str]:
        items = [i for i in (part.strip() for part in text.split(",")) if i]
        StudentProfile.from_inputs(stream="x", al=[], cgt=30, admission_district="x", home="x", ol=items)
        return items

    stream = _ask("Stream (e.g. Physical Science, Biological Science, Commerce, Arts)", need, reader=reader)
    al_items = _ask("A/L subjects and grades (comma separated)", al, reader=reader)
    cgt = _ask("Common General Test mark %", lambda t: int(t), "30", reader=reader)
    ol_items = _ask("O/L grades: Science, English, Maths (e.g. Science B, English B, Maths A)", ol, reader=reader)
    z = _ask("Z-score (optional, used in the next step)", lambda t: float(t) if t else None, "", reader=reader)
    district = _ask("Admission district (the district of your school / exam, handbook §1.5)",
                    finder.resolve_admission_district, reader=reader)
    home = _ask("Home town / DS division (for travel times)",
                lambda t: finder.resolve_origin(t).ds_division, reader=reader)
    return StudentProfile.from_inputs(stream=stream, al=al_items, cgt=cgt, admission_district=district,
                                      home=home, ol=ol_items, z_score=z)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stream")
    parser.add_argument("--al", action="append", default=[], help="A/L 'Subject:Grade' (three times)")
    parser.add_argument("--cgt", type=int, default=30, help="Common General Test mark %% (default 30)")
    parser.add_argument("--admission-district", "--district", dest="admission_district",
                        help="District for university admission (§1.5: school/exam district); "
                             "may differ from the home town's district")
    parser.add_argument("--home", help="Home town / DS division")
    parser.add_argument("--ol", action="append", default=[], help="O/L 'Subject:Grade' (Science, English, Maths, ...)")
    parser.add_argument("--z-score", type=float)
    parser.add_argument("--max-car-min", type=float, help="Only offerings within this many car minutes")
    parser.add_argument("--show-not-eligible", action="store_true", help="Also list A/L-ineligible courses with reasons")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", type=Path, help="Write the full result as JSON to this file")
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--travel-db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)

    finder = CourseFinder(args.graph, args.travel_db)
    try:
        if args.stream or args.al:
            missing = [n for n, v in (("--stream", args.stream), ("--admission-district", args.admission_district),
                                      ("--home", args.home)) if not v]
            if missing or len(args.al) != 3:
                parser.error("give --stream, three --al, --admission-district and --home (or run with no flags "
                             "for questions)")
            profile = StudentProfile.from_inputs(stream=args.stream, al=args.al, cgt=args.cgt,
                                                 admission_district=args.admission_district,
                                                 home=args.home, ol=args.ol,
                                                 z_score=args.z_score)
        else:
            if not sys.stdin.isatty():
                parser.error("no student details given; pass flags or run in a terminal for questions")
            profile = interactive_profile(finder)
            print()
        result = finder.find_courses(profile)
    except ProfileError as exc:
        hint = f" Did you mean: {', '.join(exc.suggestions[:6])}?" if exc.suggestions else ""
        parser.exit(1, f"{exc}.{hint}\n")
    finally:
        finder.close()

    if args.save:
        args.save.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=1))
    else:
        print(render(result, args.max_car_min, args.show_not_eligible))
        if args.save:
            print(f"\nSaved full result to {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
