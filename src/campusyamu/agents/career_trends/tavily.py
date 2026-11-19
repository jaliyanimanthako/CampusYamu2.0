"""Minimal Tavily search client returning raw page content."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from campusyamu.core import settings

from .firecrawl import _clean_url
from .models import SearchQuery, WebDocument
from .source_registry import EXCLUDED_DOMAINS, classify_domain


class TavilyClient:
    """Search with Tavily and keep each result's cleaned page content.

    Domain restrictions, recency windows, and country boosting come from the
    ``SearchQuery`` so the planner stays provider-neutral.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        search_depth: str | None = None,
        base_url: str = "https://api.tavily.com",
        timeout_seconds: int = 90,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("Set TAVILY_API_KEY before using the Tavily search client")
        # advanced = 2 credits/search with better relevance; basic = 1 credit.
        self.search_depth = search_depth or settings.get("career.tavily_search_depth") or "advanced"
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_documents(
        self,
        query: SearchQuery,
        limit: int,
    ) -> list[WebDocument]:
        topic = "news" if query.source_types == ("news",) else "general"
        payload: dict[str, Any] = {
            "query": query.text,
            "search_depth": self.search_depth,
            "topic": topic,
            "max_results": max(1, min(limit, 20)),
            "include_raw_content": "markdown",
            "include_answer": False,
            "exclude_domains": list(EXCLUDED_DOMAINS),
        }
        if query.include_domains:
            payload["include_domains"] = list(query.include_domains)
        if query.time_range:
            payload["time_range"] = query.time_range
        if query.country and topic == "general":
            payload["country"] = query.country.casefold()

        response = self._post_json("/search", payload)
        results = response.get("results")
        if not isinstance(results, list):
            raise RuntimeError("Tavily returned an invalid search response")
        documents = []
        for item in results:
            if isinstance(item, dict):
                document = _web_document(item, query, "news" if topic == "news" else "web")
                if document:
                    documents.append(document)
        return documents

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CampusYamu-CareerResearch/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Tavily HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Tavily request failed: {exc.reason}") from exc


def _web_document(
    item: dict[str, Any],
    query: SearchQuery,
    result_type: str,
) -> WebDocument | None:
    url = _clean_url(str(item.get("url") or ""))
    if not url:
        return None
    domain = (urllib.parse.urlsplit(url).hostname or "").casefold()
    source_tier, trusted = classify_domain(domain)
    snippet = str(item.get("content") or "").strip()
    return WebDocument(
        url=url,
        title=str(item.get("title") or "").strip(),
        description=snippet,
        # Fall back to Tavily's extract when the full page could not be parsed.
        markdown=str(item.get("raw_content") or "").strip() or snippet,
        query=query.text,
        query_category=query.category,
        result_type=result_type,
        domain=domain,
        source_tier=source_tier,
        trusted=trusted,
    )
