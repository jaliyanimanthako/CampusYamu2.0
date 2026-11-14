"""Command-line adapter for course-scoped web collection."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .environment import load_environment
from .models import WebResearchRequest
from .providers import (
    WEB_PROVIDERS,
    build_career_discovery,
    build_community_crawler,
    build_web_crawler,
    web_provider_name,
)
from .web_research import CareerWebResearchAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover and scrape career evidence for one or more courses."
    )
    parser.add_argument(
        "--course",
        action="append",
        required=True,
        help="Course name; repeat this option to research multiple courses",
    )
    parser.add_argument("--region", default="Sri Lanka", help="Target local market")
    parser.add_argument(
        "--results-per-query",
        type=int,
        default=3,
        help="Firecrawl results requested for each search query",
    )
    parser.add_argument(
        "--max-sources",
        "--limit",
        dest="max_sources",
        type=int,
        default=20,
        help="Maximum unique scraped pages retained for each course",
    )
    parser.add_argument(
        "--content-limit",
        type=int,
        default=8_000,
        help="Maximum Markdown characters retained from each page",
    )
    parser.add_argument("--env-file", type=Path, help="Path to a custom .env file")
    parser.add_argument(
        "--provider",
        choices=WEB_PROVIDERS,
        help="Web search provider (default: career.search_provider in settings, else tavily if "
        "TAVILY_API_KEY is set, else firecrawl)",
    )
    parser.add_argument(
        "--no-discovery",
        action="store_true",
        help="Skip web-search career discovery and use only the built-in job lists",
    )
    parser.add_argument(
        "--no-reddit",
        action="store_true",
        help="Skip Reddit community signals even when APIFY_API_TOKEN is set",
    )
    parser.add_argument("--refresh", action="store_true", help="Bypass cached results")
    parser.add_argument("--quiet", action="store_true", help="Hide search progress")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        load_environment(args.env_file)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    try:
        provider = web_provider_name(args.provider)
    except ValueError as exc:
        parser.error(str(exc))
    required_key = {"tavily": "TAVILY_API_KEY", "firecrawl": "FIRECRAWL_API_KEY"}[provider]
    if not os.getenv(required_key):
        parser.error(f"{required_key} is missing from the environment or .env file")

    try:
        request = WebResearchRequest(
            courses=tuple(args.course),
            region=args.region,
            results_per_query=args.results_per_query,
            max_sources_per_course=args.max_sources,
            content_char_limit=args.content_limit,
        )
    except ValueError as exc:
        parser.error(str(exc))

    progress = None if args.quiet else show_progress
    community = None if args.no_reddit else build_community_crawler()
    web_crawler = build_web_crawler(provider)
    discovery = None if args.no_discovery else build_career_discovery(web_crawler)
    if not args.quiet:
        reddit = "on" if community else (
            "off (--no-reddit)" if args.no_reddit else "off (APIFY_API_TOKEN not set)"
        )
        careers = "on" if discovery else (
            "off (--no-discovery)" if args.no_discovery else "off (OpenAI not configured)"
        )
        print(
            f"Web search: {provider} | Reddit: {reddit} | Career discovery: {careers}",
            file=sys.stderr,
        )
    result = CareerWebResearchAgent(
        web_crawler,
        community_crawler=community,
        career_discovery=discovery,
    ).research(
        request,
        refresh=args.refresh,
        on_progress=progress,
    )
    print(json.dumps(result, indent=2) if args.as_json else format_answer(result))
    return 1 if result["status"] == "failed" else 0


def show_progress(event: dict[str, Any]) -> None:
    """Print live search progress to stderr, leaving JSON stdout valid."""

    event_type = event["event"]
    if event_type == "research_started":
        message = (
            f"Running {event['query_count']} searches concurrently for "
            f"{event['course_count']} course(s)..."
        )
    elif event_type == "query_started":
        message = f"[{event['course']}] Searching {event['category']}: {event['query']}"
    elif event_type == "discovery_started":
        message = f"[{event['course']}] Discovering career paths from the web..."
    elif event_type == "discovery_completed":
        message = (
            f"[{event['course']}] Career paths ({event['status']}): "
            f"{', '.join(event['titles'])}"
            + (
                f" | Emerging areas: {', '.join(event['emerging_areas'])}"
                if event.get("emerging_areas")
                else ""
            )
        )
    elif event_type == "discovery_failed":
        message = (
            f"[{event['course']}] Career discovery failed, using built-in job list: "
            f"{event['error']}"
        )
    elif event_type == "query_completed":
        message = (
            f"[{event['course']}] Collected {event['result_count']} page(s) "
            f"for {event['category']} in {event.get('seconds', '?')}s"
        )
    else:
        message = (
            f"[{event['course']}] Search failed for {event['category']}: "
            f"{event['error']}"
        )
    print(message, file=sys.stderr, flush=True)


def format_answer(result: dict[str, Any]) -> str:
    lines = [
        f"Web collection: {result['status'].replace('_', ' ')}",
        f"Region: {result['input']['region']}",
    ]
    for course in result["course_research"]:
        collection = course["collection"]
        lines.extend(
            (
                "",
                f"{course['course']} ({course['status'].replace('_', ' ')})",
                f"Category: {course['course_category']}",
                f"Occupation terms: {', '.join(course['occupation_search_terms'])}",
                (
                    f"Sources: {collection['retained_after_deduplication']} retained, "
                    f"{collection['trusted_sources']} trusted"
                ),
            )
        )
        for document in course["documents"]:
            trust = "trusted" if document["trusted"] else "unverified"
            title = document["title"] or document["domain"]
            lines.append(f"  - [{document['source_tier']}, {trust}] {title}")
            lines.append(f"    {document['url']}")
        coverage = collection["category_coverage"]
        missing = [
            query["category"]
            for query in course["queries"]
            if coverage.get(query["category"], 0) == 0
        ]
        if missing:
            lines.append(f"  No retained evidence for: {', '.join(missing)}")
        if course["failures"]:
            lines.append(f"  Failed searches: {len(course['failures'])}")
    lines.extend(("", "Raw web data only: analytics and SWOT were not performed."))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
