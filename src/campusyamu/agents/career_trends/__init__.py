"""Course-scoped web evidence collection for CampusYamu."""

from .apify_reddit import ApifyRedditClient
from .career_discovery import CareerDiscovery
from .firecrawl import FirecrawlClient, WebSearchCrawler
from .tavily import TavilyClient
from .future_analytics import FutureCareerAnalyticsAgent
from .models import CourseProfile, SearchQuery, WebDocument, WebResearchRequest
from .pipeline import CareerTrendsPipeline
from .research_harness import ResearchHarness
from .openai_client import OpenAIResponsesClient, StructuredAnalyticsModel
from .web_research import CareerWebResearchAgent

__all__ = [
    "CareerDiscovery",
    "CareerTrendsPipeline",
    "ApifyRedditClient",
    "CareerWebResearchAgent",
    "CourseProfile",
    "FirecrawlClient",
    "FutureCareerAnalyticsAgent",
    "OpenAIResponsesClient",
    "ResearchHarness",
    "SearchQuery",
    "StructuredAnalyticsModel",
    "TavilyClient",
    "WebDocument",
    "WebResearchRequest",
    "WebSearchCrawler",
]
