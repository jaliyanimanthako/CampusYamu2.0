"""CLI for future SWOT analysis of an existing web-evidence file."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .environment import load_environment
from .future_analytics import FutureCareerAnalyticsAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a cited future SWOT from collected career evidence."
    )
    parser.add_argument(
        "--evidence",
        required=True,
        type=Path,
        help="JSON file produced by career_trends_agent.cli",
    )
    parser.add_argument(
        "--horizon-years",
        type=int,
        choices=(4, 5),
        default=5,
        help="Years until the student is expected to enter the job market",
    )
    parser.add_argument("--env-file", type=Path, help="Path to a custom .env file")
    parser.add_argument("--quiet", action="store_true", help="Hide analysis progress")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        load_environment(args.env_file)
        web_result = json.loads(args.evidence.read_text())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is missing from the environment or .env file")
    if not os.getenv("OPENAI_MODEL"):
        parser.error("OPENAI_MODEL is missing from the environment or .env file")

    progress = None if args.quiet else show_progress
    try:
        result = FutureCareerAnalyticsAgent().analyze(
            web_result,
            horizon_years=args.horizon_years,
            on_progress=progress,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2) if args.as_json else format_answer(result))
    return 1 if result["status"] == "failed" else 0


def show_progress(event: dict[str, Any]) -> None:
    event_type = event["event"]
    if event_type == "analysis_started":
        message = f"Analyzing {event['course_count']} course(s)..."
    elif event_type == "course_started":
        message = f"[{event['course']}] Building future SWOT..."
    elif event_type == "course_completed":
        message = f"[{event['course']}] Future SWOT completed"
    else:
        message = f"[{event['course']}] Analysis failed: {event['error']}"
    print(message, file=sys.stderr, flush=True)


def format_answer(result: dict[str, Any]) -> str:
    lines = [
        f"Future career analysis: {result['status'].replace('_', ' ')}",
        f"Horizon: {result['horizon_years']} years",
        f"Model: {result['model']}",
    ]
    for course in result["course_analyses"]:
        lines.extend(("", f"{course['course']} ({course['status']})"))
        if course["status"] != "success":
            lines.append(f"  Error: {course['error']}")
            continue
        intro = course.get("course_introduction")
        if intro:
            lines.append(f"  About this degree: {intro['overview']}")
            if intro["career_paths"]:
                lines.append("  What you can do after it:")
                for path in intro["career_paths"]:
                    lines.append(f"    - {path['role']}: {path['what_you_do']}")
            lines.append("")
        lines.append(
            f"  Overall: {course['overall_outlook']['label'].replace('_', ' ')} "
            f"({course['overall_outlook']['confidence']} confidence)"
        )
        lines.append(f"  {course['overall_outlook']['summary']}")
        geography = course.get("local_vs_overseas")
        if geography:
            lines.append(
                f"  Where the opportunities are: "
                f"{geography['label'].replace('_', ' ')}. {geography['explanation']}"
            )
        study = course.get("further_study")
        if study:
            lines.append(f"  Further study: {study['role']}. {study['explanation']}")
        for category, findings in course["future_swot"].items():
            lines.append(f"  {category.title()}:")
            if not findings:
                lines.append("    - Insufficient evidence")
            for finding in findings:
                refs = ", ".join(finding["evidence_refs"])
                lines.append(f"    - {finding['finding']} [{refs}]")
        niches = course.get("niche_specialisations")
        if niches:
            lines.append("  Smaller areas worth knowing about:")
            for niche in niches:
                refs = ", ".join(niche["evidence_refs"])
                lines.append(f"    - {niche['area']}: {niche['why_it_matters']} [{refs}]")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
