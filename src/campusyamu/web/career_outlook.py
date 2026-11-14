"""Career outlooks from the web agent (agents.career_trends), cached per course.

The career pipeline (web search + Reddit + research agent + cited future SWOT)
takes minutes and several paid API calls, so it runs once per course and the
result is stored in data/cache/career_outlooks/<course>.json. The course chat reads
that file as one more cited source; the raw web pages are not kept, only the
analysis and its evidence index (titles and URLs).

Run it from the chat ("Research careers for this course") or beforehand:

    uv run python -m campusyamu.web.career_outlook --course "Quantity Surveying"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from campusyamu.core import settings

from campusyamu.core.paths import CACHE_DIR

DEFAULT_DIR = CACHE_DIR / "career_outlooks"
REGION = settings.get("career.region", "Sri Lanka")


def slug(course: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", course.casefold()).strip("-") or "course"


def compact(result: dict[str, Any], course: str) -> dict[str, Any]:
    """Keep what the chat needs from a pipeline result: the analysis and its evidence index."""

    analysis = next((a for a in result.get("course_analyses", []) if a.get("course") == course),
                    (result.get("course_analyses") or [{}])[0])
    collection = next((c for c in result.get("collection", []) if c.get("course") == course), {})
    return {
        "course": course,
        "region": REGION,
        "generated_at": result.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "status": result.get("status"),
        "model": (result.get("sources") or {}).get("model"),
        "web_source": (result.get("sources") or {}).get("web"),
        "horizon_years": (result.get("input") or {}).get("horizon_years"),
        "collection": {k: collection.get(k) for k in ("retained_after_deduplication", "trusted_sources",
                                                      "career_paths", "emerging_areas")},
        "analysis": {k: v for k, v in analysis.items() if k not in ("evidence_index",)},
        "evidence_index": analysis.get("evidence_index", []),
    }


class CareerOutlookStore:
    def __init__(self, directory: Path = DEFAULT_DIR) -> None:
        self.directory = Path(directory)

    def path(self, course: str) -> Path:
        return self.directory / f"{slug(course)}.json"

    def get(self, course: str) -> dict[str, Any] | None:
        try:
            return json.loads(self.path(course).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save(self, outlook: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(outlook["course"])
        path.write_text(json.dumps(outlook, ensure_ascii=False, indent=1), encoding="utf-8")
        return path


def missing_keys() -> list[str]:
    from campusyamu.agents.career_trends.providers import web_provider_name

    try:
        provider = web_provider_name(None)
    except ValueError as exc:
        return [str(exc)]
    search_key = {"tavily": "TAVILY_API_KEY", "firecrawl": "FIRECRAWL_API_KEY"}.get(provider, "TAVILY_API_KEY")
    return [k for k in (search_key, "OPENAI_API_KEY") if not os.getenv(k)]


def run_research(course: str, on_progress: Callable[[dict[str, Any]], None] | None = None,
                 reddit: bool = True, agent: bool = True) -> dict[str, Any]:
    """The same pipeline as `campusyamu.agents.career_trends.pipeline_cli`, for one course."""

    from campusyamu.agents.career_trends.future_analytics import FutureCareerAnalyticsAgent
    from campusyamu.agents.career_trends.harness import OpenAIToolModel
    from campusyamu.agents.career_trends.models import WebResearchRequest
    from campusyamu.agents.career_trends.pipeline import CareerTrendsPipeline
    from campusyamu.agents.career_trends.providers import (build_career_discovery, build_community_crawler,
                                               build_web_crawler, web_provider_name)
    from campusyamu.agents.career_trends.research_harness import ResearchHarness
    from campusyamu.agents.career_trends.web_research import CareerWebResearchAgent

    web_crawler = build_web_crawler(web_provider_name(None))
    pipeline = CareerTrendsPipeline(
        CareerWebResearchAgent(web_crawler, community_crawler=build_community_crawler() if reddit else None,
                               career_discovery=build_career_discovery(web_crawler)),
        FutureCareerAnalyticsAgent(),
        ResearchHarness(web_crawler, OpenAIToolModel()) if agent else None,
    )
    request = WebResearchRequest(courses=(course,), region=REGION)
    return pipeline.run(request, horizon_years=settings.get("career.horizon_years", 5), on_progress=on_progress)


class CareerResearchJobs:
    """One background research run at a time; status is polled by the page (GET /v1/career-outlook).

    start(course) runs career research only. start(course, offering) - what the course chat does, with the
    course row (uni_code, course_code, course_name, university) - runs the full course research
    (course_research.py): career trends + the university's website + its specialisations, in parallel.
    """

    def __init__(self, store: CareerOutlookStore, runner: Callable[..., dict[str, Any]] = run_research,
                 websites: Any = None) -> None:
        self.store = store
        self.runner = runner
        self.websites = websites                    # UniversityPages; None = career research only
        self.jobs: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def status(self, course: str) -> dict[str, Any] | None:
        return self.jobs.get(slug(course))

    def start(self, course: str, offering: dict[str, Any] | None = None) -> tuple[bool, str]:
        full = bool(offering and offering.get("uni_code") and self.websites is not None and self.websites.enabled)
        with self.lock:
            busy = [j for j in self.jobs.values() if j["state"] == "running"]
            if busy:
                return False, f"Already researching {busy[0]['course']}; try again when it finishes"
            job = {"course": course, "state": "running", "started": time.time(), "message": "starting…",
                   "scope": "course" if full else "career"}
            self.jobs[slug(course)] = job
        target, args = (self._run_full, (dict(offering), job)) if full else (self._run, (course, job))
        threading.Thread(target=target, args=args, daemon=True).start()
        return True, "started"

    def _run_full(self, offering: dict[str, Any], job: dict[str, Any]) -> None:
        from .course_research import CourseResearch

        def event(agent: str, message: str) -> None:
            job["message"] = f"{agent}: {message}"[:160]

        try:
            out = CourseResearch(self.websites, self.store, career_runner=self.runner, on_event=event).run(offering)
            states = {name: r["state"] for name, r in out["results"].items()}
            if all(s in ("failed", "skipped") for s in states.values()) and "failed" in states.values():
                raise RuntimeError("; ".join(f"{n}: {r.get('error') or r.get('reason')}"
                                             for n, r in out["results"].items()))
            job.update(state="done", finished=time.time(), parts=states,
                       message="research ready: " + ", ".join(f"{n} {s}" for n, s in states.items()))
        except Exception as exc:                        # report to the page, keep the server up
            job.update(state="failed", message=str(exc)[:200], finished=time.time())

    def _run(self, course: str, job: dict[str, Any]) -> None:
        def progress(event: dict[str, Any]) -> None:
            kind = event.get("event", "")
            detail = event.get("query") or event.get("category") or event.get("status") or ""
            job["message"] = f"{kind.replace('_', ' ')}{': ' + str(detail)[:80] if detail else ''}"

        try:
            result = self.runner(course, on_progress=progress)
            if result.get("status") == "failed":
                raise RuntimeError("the career pipeline failed (see server log)")
            self.store.save(compact(result, course))
            job.update(state="done", message="career research ready", finished=time.time())
        except Exception as exc:                        # report to the page, keep the server up
            job.update(state="failed", message=str(exc)[:200], finished=time.time())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--course", action="append", required=True, help="KG course name (repeatable)")
    parser.add_argument("--no-reddit", action="store_true")
    parser.add_argument("--no-agent", action="store_true")
    args = parser.parse_args(argv)
    from campusyamu.agents.career_trends.environment import load_environment

    load_environment(None)
    if missing := missing_keys():
        parser.error("missing from .env: " + ", ".join(missing))
    store = CareerOutlookStore()
    for course in args.course:
        print(f"Researching {course} …", file=sys.stderr)
        result = run_research(course, lambda e: print("  " + e.get("event", ""), file=sys.stderr),
                              reddit=not args.no_reddit, agent=not args.no_agent)
        print(f"  status: {result.get('status')} -> {store.save(compact(result, course))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
