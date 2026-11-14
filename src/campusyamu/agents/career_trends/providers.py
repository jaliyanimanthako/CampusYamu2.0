"""Pick search and community collectors from the environment."""

from __future__ import annotations

import os

from campusyamu.core import settings

from .apify_reddit import ApifyRedditClient
from .career_discovery import CareerDiscovery
from .firecrawl import FirecrawlClient, WebSearchCrawler
from .tavily import TavilyClient


WEB_PROVIDERS = ("tavily", "firecrawl")


def web_provider_name(provider: str | None = None) -> str:
    """Explicit choice, then career.search_provider in settings.yaml, then whichever key is present."""

    name = (provider or settings.get("career.search_provider") or "").strip().casefold()
    if not name:
        name = "tavily" if os.getenv("TAVILY_API_KEY") else "firecrawl"
    if name not in WEB_PROVIDERS:
        raise ValueError(f"Unknown search provider {name!r}; use one of {WEB_PROVIDERS}")
    return name


def build_web_crawler(provider: str | None = None) -> WebSearchCrawler:
    if web_provider_name(provider) == "tavily":
        return TavilyClient()
    return FirecrawlClient()


def build_career_discovery(crawler: WebSearchCrawler) -> CareerDiscovery | None:
    """Web-search career discovery; needs an OpenAI model to read the pages.

    models.career_discovery in settings.yaml may name a cheaper model for this
    simple extraction step.
    """

    if not os.getenv("OPENAI_API_KEY"):
        return None
    from .openai_client import OpenAIResponsesClient

    model = OpenAIResponsesClient(model=settings.model("career_discovery"))
    return CareerDiscovery(crawler, model)


def build_community_crawler() -> WebSearchCrawler | None:
    """Reddit via Apify when a token is configured; otherwise skip quietly."""

    if os.getenv("APIFY_API_TOKEN"):
        return ApifyRedditClient()
    return None
