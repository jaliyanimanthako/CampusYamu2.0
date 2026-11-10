"""End-to-end behavior check using a fake crawler and real aggregation."""

import unittest

from career_trends_agent import (
    CareerSignal,
    CareerTrendRequest,
    CareerTrendsAgent,
    TrendSource,
)


SOURCES = (
    TrendSource("global", "Global outlook", "https://example.com/global", "global", "jobs"),
    TrendSource("official", "Official projections", "https://example.com/data", "US", "jobs"),
    TrendSource("broken", "Unavailable source", "https://example.com/error", "global", "jobs"),
)


class FakeCrawler:
    def __init__(self) -> None:
        self.calls = 0

    def extract_signals(self, source, request):
        self.calls += 1
        if source.source_id == "broken":
            raise RuntimeError("source unavailable")
        return [
            CareerSignal(
                occupation="Data Scientists",
                direction="growing",
                evidence=f"{source.name} reports growth.",
                source=source,
                skills=("analytical thinking", "programming"),
                related_studies=(request.study_stream,),
                ai_exposure="high",
                metric="positive projected growth",
                publication_date="2025",
            )
        ]


class CareerTrendsAgentTest(unittest.TestCase):
    def test_grounded_results_failures_and_cache(self) -> None:
        crawler = FakeCrawler()
        agent = CareerTrendsAgent(crawler, sources=SOURCES)
        request = CareerTrendRequest(
            study_stream="Physical Science",
            subjects=("Combined Mathematics", "Physics", "Chemistry"),
            region="global",
        )

        result = agent.research(request)
        cached_result = agent.research(request)

        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["sources"], {"attempted": 3, "succeeded": 2, "failed": 1})
        self.assertEqual(result["careers"][0]["outlook"], "strong_growth")
        self.assertEqual(result["careers"][0]["evidence_confidence"], "medium")
        self.assertEqual(result["careers"][0]["source_count"], 2)
        self.assertEqual(len(result["careers"][0]["evidence"]), 2)
        self.assertEqual(cached_result["careers"], result["careers"])
        self.assertEqual(crawler.calls, 4)


if __name__ == "__main__":
    unittest.main()
