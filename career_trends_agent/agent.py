"""Public career-trends agent with bounded crawling and deterministic synthesis."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Sequence

from .aggregation import aggregate_signals
from .firecrawl import FirecrawlClient, TrendCrawler
from .models import CareerSignal, CareerTrendRequest, TrendSource
from .sources import sources_for_region


class CareerTrendsAgent:
    """Collect current evidence and rank career signals for a study profile."""

    def __init__(
        self,
        crawler: TrendCrawler | None = None,
        *,
        sources: Sequence[TrendSource] | None = None,
        cache_ttl_seconds: int = 86_400,
        max_workers: int = 4,
    ) -> None:
        self.crawler = crawler or FirecrawlClient()
        self.sources = tuple(sources) if sources is not None else None
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_workers = max_workers
        self._cache: dict[str, tuple[float, list[CareerSignal]]] = {}

    def research(
        self,
        request: CareerTrendRequest,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        sources = self.sources or sources_for_region(request.region)
        signals: list[CareerSignal] = []
        failures: list[dict[str, str]] = []
        succeeded_sources: set[str] = set()

        worker_count = max(1, min(self.max_workers, len(sources)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            pending = {
                executor.submit(self._collect, source, request, refresh): source
                for source in sources
            }
            for future in as_completed(pending):
                source = pending[future]
                try:
                    source_signals = future.result()
                    signals.extend(source_signals)
                    succeeded_sources.add(source.source_id)
                except Exception as exc:
                    failures.append(
                        {
                            "source_id": source.source_id,
                            "source": source.name,
                            "url": source.url,
                            "error": str(exc),
                        }
                    )

        if not signals:
            status = "failed"
        elif failures:
            status = "partial_failure"
        else:
            status = "success"
        return {
            "status": status,
            "input": request.to_dict(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "curated_firecrawl_extraction_with_deterministic_aggregation",
            "careers": aggregate_signals(signals, request.max_careers),
            "sources": {
                "attempted": len(sources),
                "succeeded": len(succeeded_sources),
                "failed": len(failures),
            },
            "failures": sorted(failures, key=lambda item: item["source_id"]),
            "caveat": (
                "Career trends are evidence inputs, not guarantees. AI exposure "
                "describes task transformation and does not by itself mean job loss."
            ),
        }

    def _collect(
        self,
        source: TrendSource,
        request: CareerTrendRequest,
        refresh: bool,
    ) -> list[CareerSignal]:
        cache_key = self._cache_key(source, request)
        cached = self._cache.get(cache_key)
        if not refresh and cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        signals = self.crawler.extract_signals(source, request)
        self._cache[cache_key] = (time.monotonic(), signals)
        return signals

    @staticmethod
    def _cache_key(source: TrendSource, request: CareerTrendRequest) -> str:
        subjects = "|".join(subject.casefold() for subject in request.subjects)
        return "::".join(
            (
                source.source_id,
                request.study_stream.casefold(),
                subjects,
                request.region.casefold(),
            )
        )
