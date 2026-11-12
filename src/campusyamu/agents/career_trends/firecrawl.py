"""Minimal Firecrawl v2 search-and-scrape client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from .models import SearchQuery, WebDocument
from .source_registry import classify_domain


TIME_FILTERS = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}


class WebSearchCrawler(Protocol):
    def search_documents(
        self,
        query: SearchQuery,
        limit: int,
    ) -> list[WebDocument]: ...


class FirecrawlClient:
    """Call Firecrawl directly without adding a large SDK dependency."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.firecrawl.dev/v2",
        timeout_seconds: int = 120,
    ) -> None:
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("Set FIRECRAWL_API_KEY before using the live crawler")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_documents(
        self,
        query: SearchQuery,
        limit: int,
    ) -> list[WebDocument]:
        """Search and return raw Markdown without analytical extraction."""

        text = query.text
        if query.include_domains:
            text += " (" + " OR ".join(f"site:{d}" for d in query.include_domains) + ")"
        payload: dict[str, Any] = {
            "query": text,
            "limit": limit,
            "sources": [{"type": value} for value in query.source_types],
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        }
        if query.time_range in TIME_FILTERS:
            payload["tbs"] = TIME_FILTERS[query.time_range]
        response = self._post_json("/search", payload)
        if not response.get("success"):
            raise RuntimeError(str(response.get("error") or "Firecrawl search failed"))
        items = _search_items(response.get("data"), query.source_types)
        if items is None:
            raise RuntimeError("Firecrawl returned an invalid search response")

        documents = []
        for item, result_type in items:
            if not isinstance(item, dict):
                continue
            document = _web_document(item, query, result_type)
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
            raise RuntimeError(f"Firecrawl HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Firecrawl request failed: {exc.reason}") from exc


def _web_document(
    payload: dict[str, Any],
    query: SearchQuery,
    result_type: str,
) -> WebDocument | None:
    metadata = payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    raw_url = payload.get("url") or metadata.get("sourceURL") or metadata.get("url")
    url = _clean_url(str(raw_url or ""))
    if not url:
        return None
    domain = (urllib.parse.urlsplit(url).hostname or "").casefold()
    source_tier, trusted = classify_domain(domain)
    return WebDocument(
        url=url,
        title=str(payload.get("title") or metadata.get("title") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        markdown=str(payload.get("markdown") or "").strip(),
        query=query.text,
        query_category=query.category,
        result_type=result_type,
        domain=domain,
        source_tier=source_tier,
        trusted=trusted,
    )


def _search_items(
    data: Any,
    source_types: tuple[str, ...],
) -> list[tuple[Any, str]] | None:
    if isinstance(data, list):
        return [(item, source_types[0]) for item in data]
    if not isinstance(data, dict):
        return None
    items = []
    for source_type in source_types:
        source_items = data.get(source_type, [])
        if not isinstance(source_items, list):
            return None
        items.extend((item, source_type) for item in source_items)
    return items


def _clean_url(raw_url: str) -> str:
    if not raw_url.startswith(("https://", "http://")):
        return ""
    parts = urllib.parse.urlsplit(raw_url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if not key.casefold().startswith("utm_")]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc.casefold(), parts.path, urllib.parse.urlencode(query), "")
    )
