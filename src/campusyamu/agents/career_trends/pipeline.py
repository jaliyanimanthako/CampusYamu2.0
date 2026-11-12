"""End-to-end career outlook: course names in, cited future SWOT out."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable

from .future_analytics import FutureCareerAnalyticsAgent
from .models import WebResearchRequest
from .research_harness import ResearchHarness
from .web_research import CareerWebResearchAgent


ProgressCallback = Callable[[dict[str, Any]], None]


class CareerTrendsPipeline:
    """Collect evidence, let the research agent fill gaps, then build the SWOT.

    The research agent (``research_harness``) is optional; without it the
    fixed searches alone feed the analysis.
    """

    def __init__(
        self,
        research_agent: CareerWebResearchAgent | None = None,
        analytics_agent: FutureCareerAnalyticsAgent | None = None,
        research_harness: ResearchHarness | None = None,
    ) -> None:
        self.research_agent = research_agent or CareerWebResearchAgent()
        self.analytics_agent = analytics_agent or FutureCareerAnalyticsAgent()
        self.research_harness = research_harness

    def run(
        self,
        request: WebResearchRequest,
        *,
        horizon_years: int = 5,
        refresh: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Synchronous entry point; use ``await arun(...)`` inside async apps."""

        return asyncio.run(
            self.arun(
                request,
                horizon_years=horizon_years,
                refresh=refresh,
                on_progress=on_progress,
            )
        )

    async def arun(
        self,
        request: WebResearchRequest,
        *,
        horizon_years: int = 5,
        refresh: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        # Fail before spending search credits on an invalid request.
        if not 4 <= horizon_years <= 5:
            raise ValueError("horizon_years must be 4 or 5")

        web_result = await self.research_agent.aresearch(
            request,
            refresh=refresh,
            on_progress=on_progress,
        )
        if self.research_harness is not None:
            await self.research_harness.aenrich(web_result, on_progress)
        # The model call is blocking HTTP; keep the event loop free.
        analysis = await asyncio.to_thread(
            self.analytics_agent.analyze,
            web_result,
            horizon_years=horizon_years,
            on_progress=on_progress,
        )

        return {
            "status": _combined_status(web_result["status"], analysis["status"]),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "input": {**request.to_dict(), "horizon_years": horizon_years},
            "sources": {
                "web": web_result.get("web_source"),
                "community": web_result.get("community_source"),
                "model": analysis.get("model"),
            },
            "collection": [_collection_summary(course) for course in web_result["course_research"]],
            "course_analyses": analysis["course_analyses"],
            "web_research": web_result,
        }


def _collection_summary(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "course": course["course"],
        "status": course["status"],
        **course["collection"],
        "career_paths": course.get("occupation_search_terms", []),
        "emerging_areas": course.get("emerging_areas", []),
        "agent_research": course.get("agent_research"),
        "career_discovery": course.get("career_discovery"),
        "failed_searches": [
            {"category": failure["category"], "error": failure["error"]}
            for failure in course["failures"]
        ],
    }


def _combined_status(collection: str, analysis: str) -> str:
    if analysis == "failed":
        return "failed"
    if collection == "success" and analysis == "success":
        return "success"
    return "partial_failure"
