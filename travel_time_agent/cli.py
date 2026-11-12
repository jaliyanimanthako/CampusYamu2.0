"""Travel time from a student's DS division to university campuses.

    uv run python -m travel_time_agent --from Kantale
    uv run python -m travel_time_agent --from Kantale --university Eastern
    uv run python -m travel_time_agent --from Kantale --course Engineering   # by teaching site
    uv run python -m travel_time_agent --from Minuwangoda --faculty Engineering --university Ruhuna
    uv run python -m travel_time_agent --districts
    uv run python -m travel_time_agent --district Trincomalee      # its DS divisions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .build_db import DEFAULT_DB
from .repository import LookupError_, TravelRepository

NOTE = ("Car = free-flow driving time by road. Bus ≈ a rough public-transport estimate, "
        "not a timetable. Use both to compare campuses, not as exact journey times.")


def _hours(minutes: float) -> str:
    h, m = divmod(round(minutes), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def _format_rows(rows: list[dict], courses: bool = False) -> list[str]:
    lines = []
    for i, r in enumerate(rows, start=1):
        marks = []
        if courses and r.get("site_needs_review"):
            marks.append("teaching site to confirm")
        if r["same_district"]:
            marks.append("home district")
        if r["approximate_location"]:
            marks.append("approx. location")
        if r.get("status") == "candidate":
            marks.append("unconfirmed site")
        what = (f"{r['uni_code']} {r['course_name']} — {r['university']}, {r['campus_site']}"
                if courses else f"{r['university']} — {r['campus_site']}")
        lines.append(f"{i:>3}. car {_hours(r['drive_min']):>12} | bus ≈ {_hours(r['bus_min_est']):>12}  "
                     f"{r['road_km']:>6.1f} km  {what} [{r['campus_district']}]"
                     + (f"  ({', '.join(marks)})" if marks else ""))
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="origin", help="DS division (or its main town)")
    parser.add_argument("--in-district", help="District, to disambiguate --from")
    parser.add_argument("--university", help="Only this university's campuses")
    parser.add_argument("--course", help="Rank offerings of a course (name or code) by teaching site")
    parser.add_argument("--faculty", help="Rank sites of a faculty, e.g. Engineering or 'Faculty of Medicine'")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--all", action="store_true", help="Every campus (ignores --limit)")
    parser.add_argument("--include-candidates", action="store_true",
                        help="Include unconfirmed candidate sites (USJ Engineering)")
    parser.add_argument("--districts", action="store_true", help="List districts")
    parser.add_argument("--district", help="List the DS divisions of a district")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = TravelRepository(args.db)
    try:
        if args.districts:
            rows = repo.districts()
            print(json.dumps(rows, indent=2) if args.json else "\n".join(
                f"{r['district']:<14} {r['province']:<15} {r['ds_divisions']:>3} DS divisions, "
                f"{r['campuses']} campuses" for r in rows))
            return 0
        if args.district and not args.origin:
            origins = repo.ds_divisions(args.district)
            print(json.dumps([o.__dict__ for o in origins], indent=2) if args.json
                  else "\n".join(o.ds_division for o in origins))
            return 0
        if not args.origin:
            parser.error("give --from <DS division>, --districts or --district <name>")
        origin = repo.find_origin(args.origin, args.in_district or args.district)
        if args.faculty:
            rows = repo.faculty_sites(origin, args.faculty, args.university, None if args.all else args.limit)
            if args.json:
                print(json.dumps({"origin": origin.__dict__, "sites": rows, "note": NOTE}, indent=2))
                return 0
            print(f"From {origin.ds_division} DS division ({origin.district} district): "
                  f"sites for {args.faculty!r}" + (f" at {args.university}" if args.university else "") + "\n")
            if not rows:
                print("No matching sites.")
            for line, row in zip(_format_rows(rows), rows):
                print(line)
                if row["matching_courses"]:
                    print(f"{'':>8}teaches: {'; '.join(row['matching_courses'])}")
            print(f"\nNote: {NOTE}")
            return 0
        if args.course:
            rows = repo.course_offerings(origin, args.course, None if args.all else args.limit)
            if args.json:
                print(json.dumps({"origin": origin.__dict__, "offerings": rows, "note": NOTE}, indent=2))
                return 0
            print(f"From {origin.ds_division} DS division ({origin.district} district): "
                  f"offerings matching {args.course!r}, by travel time to the teaching site\n")
            print("\n".join(_format_rows(rows, courses=True)) or "No matching offerings.")
            print(f"\nNote: {NOTE}")
            return 0
        rows = repo.from_origin(origin, args.university, None if args.all else args.limit,
                                args.include_candidates)
        summary = repo.summary(origin)
        if args.json:
            print(json.dumps({"summary": summary, "campuses": rows, "note": NOTE}, indent=2))
            return 0
        print(f"From {origin.ds_division} DS division ({origin.district} district, {origin.province} Province)\n")
        print("\n".join(_format_rows(rows)))
        if summary["nearest_is_outside_home_district"]:
            home = summary["nearest_in_home_district"]
            if home:
                print(f"\nNearest campus is outside {origin.district} district — "
                      f"{_hours(summary['minutes_saved_vs_home_district'])} closer than the nearest "
                      f"home-district campus ({home['campus_site']}, {_hours(home['drive_min'])}).")
            else:
                print(f"\n{origin.district} district has no campus; the nearest is in "
                      f"{summary['nearest']['campus_district']}.")
        print(f"\nNote: {NOTE}")
        return 0
    except LookupError_ as exc:
        hint = f" Did you mean: {', '.join(exc.suggestions)}?" if exc.suggestions else ""
        parser.exit(1, f"{exc}.{hint}\n")
    finally:
        repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
