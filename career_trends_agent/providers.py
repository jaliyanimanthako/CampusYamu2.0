"""Pick search and community collectors from the environment."""

from __future__ import annotations

import os

from .apify_reddit import ApifyRedditClient
from .career_discovery import CareerDiscovery
from .firecrawl import FirecrawlClient, WebSearchCrawler
from .tavily import TavilyClient


WEB_PROVIDERS = ("tavily", "firecrawl")


def web_provider_name(provider: str | None = None) -> str:
    """Explicit choice, then SEARCH_PROVIDER, then whichever key is present."""

    name = (provider or os.getenv("SEARCH_PROVIDER") or "").strip().casefold()
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

    DISCOVERY_MODEL may name a cheaper model than OPENAI_MODEL for this
    simple extraction step.
    """

    if not (os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")):
        return None
    from .openai_client import OpenAIResponsesClient

    model = OpenAIResponsesClient(model=os.getenv("DISCOVERY_MODEL") or None)
    return CareerDiscovery(crawler, model)


def build_community_crawler() -> WebSearchCrawler | None:
    """Reddit via Apify when a token is configured; otherwise skip quietly."""

    if os.getenv("APIFY_API_TOKEN"):
        return ApifyRedditClient()
    return None
