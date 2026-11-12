"""Course-scoped web discovery and raw page collection."""

from __future__ import annotations

import asyncio
import inspect
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .career_discovery import (
    CareerDiscovery,
    DiscoveryResult,
    discovery_query,
    merge_profile,
)
from .course_taxonomy import profile_for
from .firecrawl import WebSearchCrawler
from .models import CourseProfile, SearchQuery, WebDocument, WebResearchRequest
from .search_planner import COMMUNITY_SOURCE, build_search_queries
from .web_results import course_status, document_dict, overall_status, select_documents


ProgressCallback = Callable[[dict[str, Any]], None]


class CareerWebResearchAgent:
    """Discover and scrape web pages without producing career conclusions.

    All searches run concurrently on one event loop. Web searches and the
    community (Reddit) collector have separate concurrency limits, so a slow
    Apify actor run never delays the web searches.
    """

    def __init__(
        self,
        crawler: WebSearchCrawler | None = None,
        *,
        community_crawler: WebSearchCrawler | None = None,
        career_discovery: CareerDiscovery | None = None,
        cache_ttl_seconds: int = 86_400,
        max_concurrency: int = 6,
        community_concurrency: int = 2,
    ) -> None:
        if crawler is None:
            from .providers import build_web_crawler

            crawler = build_web_crawler()
        self.crawler = crawler
        self.community_crawler = community_crawler
        self.career_discovery = career_discovery
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_concurrency = max_concurrency
        self.community_concurrency = community_concurrency
        self._cache: dict[str, tuple[float, list[WebDocument]]] = {}

    def research(
        self,
        request: WebResearchRequest,
        *,
        refresh: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Synchronous entry point for scripts and the CLI.

        Inside an existing event loop (FastAPI, notebooks), ``await
        aresearch(...)`` instead.
        """

        return asyncio.run(
            self.aresearch(request, refresh=refresh, on_progress=on_progress)
        )

    async def aresearch(
        self,
        request: WebResearchRequest,
        *,
        refresh: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        profiles = tuple(profile_for(course) for course in request.courses)
        searched = {profile.name: profile for profile in profiles}
        plans: dict[str, list[SearchQuery]] = {p.name: [] for p in profiles}
        documents: dict[str, list[WebDocument]] = {p.name: [] for p in profiles}
        failures: dict[str, list[dict[str, str]]] = {p.name: [] for p in profiles}
        discoveries: dict[str, dict[str, Any]] = {}
        task_count = sum(
            len(self._runnable(build_search_queries(profile, request.region)))
            for profile in profiles
        )
        _notify(
            on_progress,
            {
                "event": "research_started",
                "course_count": len(profiles),
                "query_count": task_count,
            },
        )

        web_slots = asyncio.Semaphore(max(1, self.max_concurrency))
        community_slots = asyncio.Semaphore(max(1, self.community_concurrency))

        async def run_query(course: str, query: SearchQuery) -> None:
            is_community = COMMUNITY_SOURCE in query.source_types
            async with community_slots if is_community else web_slots:
                _notify(
                    on_progress,
                    {
                        "event": "query_started",
                        "course": course,
                        "category": query.category,
                        "query": query.text,
                    },
                )
                started = time.monotonic()
                try:
                    found = await self._search(query, request.results_per_query, refresh)
                except Exception as exc:
                    failures[course].append(
                        {
                            "category": query.category,
                            "query": query.text,
                            "error": str(exc),
                        }
                    )
                    _notify(
                        on_progress,
                        {
                            "event": "query_failed",
                            "course": course,
                            "category": query.category,
                            "error": str(exc),
                        },
                    )
                    return
                documents[course].extend(found)
                _notify(
                    on_progress,
                    {
                        "event": "query_completed",
                        "course": course,
                        "category": query.category,
                        "result_count": len(found),
                        "seconds": round(time.monotonic() - started, 1),
                    },
                )

        async def run_course(profile: CourseProfile) -> None:
            name = profile.name
            base = self._runnable(build_search_queries(profile, request.region))
            community = [q for q in base if COMMUNITY_SOURCE in q.source_types]
            # Reddit searches by course name and is the slowest step: start now.
            community_run = asyncio.gather(*(run_query(name, q) for q in community))

            enriched = await self._discover(
                profile, request.region, refresh, documents, failures, discoveries, on_progress
            )
            searched[name] = enriched
            web = [
                q
                for q in self._runnable(build_search_queries(enriched, request.region))
                if COMMUNITY_SOURCE not in q.source_types
            ]
            plans[name] = [*web, *community]
            await asyncio.gather(community_run, *(run_query(name, q) for q in web))

        await asyncio.gather(*(run_course(profile) for profile in profiles))

        course_research = []
        for profile in profiles:
            raw_documents = documents[profile.name]
            retained = select_documents(
                raw_documents,
                request.max_sources_per_course,
            )
            course_research.append(
                {
                    "course": profile.name,
                    "course_category": profile.category,
                    "occupation_mapping_found": profile.mapped,
                    "occupation_search_terms": list(searched[profile.name].focus_areas),
                    "emerging_areas": list(searched[profile.name].emerging_areas),
                    "career_discovery": discoveries.get(profile.name),
                    "status": course_status(retained, failures[profile.name]),
                    "queries": [
                        {
                            "category": query.category,
                            "query": query.text,
                            "source_types": list(query.source_types),
                        }
                        for query in plans[profile.name]
                    ],
                    "collection": {
                        "discovered": len(raw_documents),
                        "retained_after_deduplication": len(retained),
                        "trusted_sources": sum(item.trusted for item in retained),
                        "category_coverage": _category_coverage(retained),
                    },
                    "documents": [
                        document_dict(item, request.content_char_limit)
                        for item in retained
                    ],
                    "failures": failures[profile.name],
                }
            )

        return {
            "status": overall_status(course_research),
            "input": request.to_dict(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "concurrent_web_search_with_raw_content_collection",
            "web_source": type(self.crawler).__name__,
            "community_source": (
                type(self.community_crawler).__name__ if self.community_crawler else None
            ),
            "course_research": course_research,
            "analytics_performed": False,
            "swot_performed": False,
        }

    async def _search(
        self,
        query: SearchQuery,
        limit: int,
        refresh: bool,
    ) -> list[WebDocument]:
        crawler = self._crawler_for(query)
        cache_key = (
            f"{type(crawler).__name__}::{limit}::{query.category}::{query.text.casefold()}"
        )
        cached = self._cache.get(cache_key)
        if not refresh and cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        native = getattr(crawler, "asearch_documents", None)
        if native is not None and inspect.iscoroutinefunction(native):
            documents = await native(query, limit)
        else:
            # Blocking HTTP clients run in worker threads so calls overlap.
            documents = await asyncio.to_thread(crawler.search_documents, query, limit)
        self._cache[cache_key] = (time.monotonic(), documents)
        return documents

    def _runnable(self, queries: tuple[SearchQuery, ...]) -> list[SearchQuery]:
        return [query for query in queries if self._crawler_for(query) is not None]

    async def _discover(
        self,
        profile: CourseProfile,
        region: str,
        refresh: bool,
        documents: dict[str, list[WebDocument]],
        failures: dict[str, list[dict[str, str]]],
        discoveries: dict[str, dict[str, Any]],
        on_progress: ProgressCallback | None,
    ) -> CourseProfile:
        """Find the jobs this course leads to; fall back to the taxonomy on failure."""

        if self.career_discovery is None:
            return profile
        name = profile.name
        taxonomy = profile.focus_areas if profile.mapped else ()
        _notify(on_progress, {"event": "discovery_started", "course": name})
        try:
            result = await asyncio.to_thread(
                self.career_discovery.discover, profile, region, refresh=refresh
            )
        except Exception as exc:
            discoveries[name] = DiscoveryResult("failed", error=str(exc)).summary(taxonomy)
            failures[name].append(
                {
                    "category": "career_paths",
                    "query": discovery_query(profile, region).text,
                    "error": str(exc),
                }
            )
            _notify(
                on_progress,
                {"event": "discovery_failed", "course": name, "error": str(exc)},
            )
            return profile
        documents[name].extend(result.documents)
        discoveries[name] = result.summary(taxonomy)
        _notify(
            on_progress,
            {
                "event": "discovery_completed",
                "course": name,
                "status": result.status,
                "titles": list(result.titles),
                "emerging_areas": list(result.emerging_areas),
            },
        )
        return merge_profile(profile, result.titles, result.emerging_areas)

    def _crawler_for(self, query: SearchQuery) -> WebSearchCrawler | None:
        if COMMUNITY_SOURCE in query.source_types:
            return self.community_crawler
        return self.crawler


def _notify(callback: ProgressCallback | None, event: dict[str, Any]) -> None:
    if callback:
        callback(event)


def _category_coverage(documents: list[WebDocument]) -> dict[str, int]:
    coverage: dict[str, int] = {}
    for document in documents:
        coverage[document.query_category] = coverage.get(document.query_category, 0) + 1
    return dict(sorted(coverage.items()))
