"""One command: course name(s) in, evidence-cited future SWOT out."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from . import analysis_cli, cli
from .environment import load_environment
from .future_analytics import FutureCareerAnalyticsAgent
from .models import WebResearchRequest
from .harness import OpenAIToolModel
from .pipeline import CareerTrendsPipeline
from .providers import (
    WEB_PROVIDERS,
    build_career_discovery,
    build_community_crawler,
    build_web_crawler,
    web_provider_name,
)
from .research_harness import ResearchHarness
from .web_research import CareerWebResearchAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research one or more courses and produce a cited future SWOT."
    )
    parser.add_argument(
        "--course",
        action="append",
        required=True,
        help="Course name; repeat this option for multiple courses",
    )
    parser.add_argument("--region", default="Sri Lanka", help="Target local market")
    parser.add_argument(
        "--horizon-years",
        type=int,
        choices=(4, 5),
        default=5,
        help="Years until the student is expected to enter the job market",
    )
    parser.add_argument("--results-per-query", type=int, default=3)
    parser.add_argument("--max-sources", type=int, default=20)
    parser.add_argument("--content-limit", type=int, default=8_000)
    parser.add_argument("--provider", choices=WEB_PROVIDERS)
    parser.add_argument("--no-reddit", action="store_true")
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help="Skip web-search career discovery and use only the built-in job lists",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignore cached career paths")
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Skip the gap-filling research agent and analyse the fixed searches only",
    )
    parser.add_argument("--agent-iterations", type=int, default=9, help="Agent loop turn limit")
    parser.add_argument("--agent-searches", type=int, default=6, help="Agent web search budget")
    parser.add_argument(
        "--save-evidence",
        type=Path,
        help="Also write the raw collected evidence to this JSON file",
    )
    parser.add_argument("--env-file", type=Path, help="Path to a custom .env file")
    parser.add_argument("--quiet", action="store_true", help="Hide progress")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the SWOT result as JSON (raw evidence goes to --save-evidence)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        load_environment(args.env_file)
        provider = web_provider_name(args.provider)
        request = WebResearchRequest(
            courses=tuple(args.course),
            region=args.region,
            results_per_query=args.results_per_query,
            max_sources_per_course=args.max_sources,
            content_char_limit=args.content_limit,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    # Check every key up front so no credits are spent on a run that cannot finish.
    search_key = {"tavily": "TAVILY_API_KEY", "firecrawl": "FIRECRAWL_API_KEY"}[provider]
    for key in (search_key, "OPENAI_API_KEY", "OPENAI_MODEL"):
        if not os.getenv(key):
            parser.error(f"{key} is missing from the environment or .env file")

    community = None if args.no_reddit else build_community_crawler()
    web_crawler = build_web_crawler(provider)
    discovery = None if args.no_discovery else build_career_discovery(web_crawler)
    harness = None
    if not args.no_agent:
        harness = ResearchHarness(
            web_crawler,
            OpenAIToolModel(),
            max_iterations=args.agent_iterations,
            max_searches=args.agent_searches,
        )
    if not args.quiet:
        print(
            f"Web search: {provider} | Reddit: {'on' if community else 'off'} | "
            f"Career discovery: {'on' if discovery else 'off'} | "
            f"Research agent: {harness.model.model if harness else 'off'} | "
            f"Model: {os.getenv('OPENAI_MODEL')}",
            file=sys.stderr,
        )
    pipeline = CareerTrendsPipeline(
        CareerWebResearchAgent(
            web_crawler,
            community_crawler=community,
            career_discovery=discovery,
        ),
        FutureCareerAnalyticsAgent(),
        harness,
    )
    result = pipeline.run(
        request,
        horizon_years=args.horizon_years,
        refresh=args.refresh,
        on_progress=None if args.quiet else show_progress,
    )

    if args.save_evidence:
        args.save_evidence.write_text(json.dumps(result["web_research"], indent=2))
        if not args.quiet:
            print(f"Raw evidence saved to {args.save_evidence}", file=sys.stderr)
    output = {key: value for key, value in result.items() if key != "web_research"}
    print(json.dumps(output, indent=2) if args.as_json else format_answer(result))
    return 1 if result["status"] == "failed" else 0


def show_progress(event: dict[str, Any]) -> None:
    if event["event"].startswith("agent_"):
        print(_agent_message(event), file=sys.stderr, flush=True)
    elif event["event"] in {"analysis_started", "course_started", "course_completed", "course_failed"}:
        analysis_cli.show_progress(event)
    else:
        cli.show_progress(event)


def _agent_message(event: dict[str, Any]) -> str:
    kind = event["event"]
    prefix = f"[{event.get('course', '?')}] Agent"
    if kind == "agent_started":
        return f"{prefix} ({event['model']}) is checking the evidence for gaps..."
    if kind == "agent_iteration":
        return f"{prefix} turn {event['iteration']}: {event['tool_calls']} tool call(s)"
    if kind == "agent_search":
        return (
            f"{prefix} searched {event['category']}: {event['query']} "
            f"-> {event['new_sources']} new"
        )
    if kind == "agent_call_rejected":
        return f"{prefix} guardrail blocked a search: {event['reason']}"
    if kind == "agent_answer_rejected":
        return f"{prefix} guardrail sent the answer back: {' | '.join(event['problems'])}"
    if kind == "agent_compacted":
        return (
            f"{prefix} context compacted "
            f"({event['chars_before']:,} -> {event['chars_after']:,} chars)"
        )
    if kind == "agent_finished":
        return f"{prefix} finished: {event['status']} after {event['iterations']} turn(s)"
    if kind == "agent_failed":
        return f"{prefix} failed, continuing without it: {event['error']}"
    return f"{prefix}: {kind}"


def format_answer(result: dict[str, Any]) -> str:
    lines = [f"Career outlook: {result['status'].replace('_', ' ')}"]
    collection = {item["course"]: item for item in result["collection"]}
    for analysis in result["course_analyses"]:
        summary = collection.get(analysis["course"], {})
        lines.append(
            f"\n{analysis['course']}: {summary.get('retained_after_deduplication', 0)} sources "
            f"({summary.get('trusted_sources', 0)} trusted), "
            f"{len(summary.get('failed_searches', []))} failed searches"
        )
        if summary.get("career_paths"):
            lines.append(f"  Career paths searched: {', '.join(summary['career_paths'])}")
        if summary.get("emerging_areas"):
            lines.append(f"  Emerging areas searched: {', '.join(summary['emerging_areas'])}")
        agent = summary.get("agent_research")
        if agent and agent.get("status") == "failed":
            lines.append(f"  Research agent: failed ({agent['error']})")
        elif agent:
            lines.append(
                f"  Research agent: {agent['status'].replace('_', ' ')} after "
                f"{agent['iterations']} turn(s), {len(agent['searches'])} search(es), "
                f"{agent['compactions']} compaction(s); added {agent['sources_added']} source(s)"
            )
            if agent["niche_areas"]:
                lines.append(
                    "  Niche areas verified: "
                    + ", ".join(area["area"] for area in agent["niche_areas"])
                )
            for gap in agent["unfilled_gaps"]:
                lines.append(f"  Not found: {gap}")
    lines.append("")
    lines.append(
        analysis_cli.format_answer(
            {
                "status": result["status"],
                "horizon_years": result["input"]["horizon_years"],
                "model": result["sources"]["model"],
                "course_analyses": result["course_analyses"],
            }
        )
    )
    for analysis in result["course_analyses"]:
        if analysis.get("status") != "success":
            continue
        lines.extend(("", f"{analysis['course']} limitations:"))
        lines.extend(f"  - {item}" for item in analysis["limitations"])
        lines.extend(("", f"{analysis['course']} sources:"))
        for source in analysis["evidence_index"]:
            trust = "trusted" if source["trusted"] else source["source_tier"]
            lines.append(f"  [{source['evidence_id']}] ({trust}) {source['title'][:80]}")
            lines.append(f"         {source['url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
