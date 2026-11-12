"""Behavior checks for web discovery without live API calls."""

import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from campusyamu.agents.career_trends import (
    ApifyRedditClient,
    CareerWebResearchAgent,
    FirecrawlClient,
    FutureCareerAnalyticsAgent,
    OpenAIResponsesClient,
    SearchQuery,
    WebDocument,
    WebResearchRequest,
)
from campusyamu.agents.career_trends.cli import build_parser, format_answer
from campusyamu.agents.career_trends.analytics_evidence import (
    _fair_shares,
    build_evidence_packet,
    cap_unverified_confidence,
)
from campusyamu.agents.career_trends.pipeline import CareerTrendsPipeline
from campusyamu.agents.career_trends.career_discovery import (
    CareerDiscovery,
    grounded_titles,
    merge_profile,
)
from campusyamu.agents.career_trends.pipeline_cli import format_answer as pipeline_format_answer
from campusyamu.agents.career_trends.apify_reddit import reddit_documents
from campusyamu.agents.career_trends.environment import load_environment
from campusyamu.agents.career_trends.providers import web_provider_name
from campusyamu.agents.career_trends.search_planner import build_search_queries
from campusyamu.agents.career_trends.course_taxonomy import profile_for
from campusyamu.agents.career_trends.source_registry import classify_domain
from campusyamu.agents.career_trends.tavily import TavilyClient
import time


class FakeWebCrawler:
    def __init__(self) -> None:
        self.calls = 0

    def search_documents(self, query, limit):
        self.calls += 1
        if query.category == "local_market":
            raise RuntimeError("search unavailable")
        return [
            WebDocument(
                url=f"https://example.com/{query.category}",
                title=f"Result for {query.category}",
                description="A test search result",
                markdown="Evidence from the scraped page about SLMC registration. " * 30,
                query=query.text,
                query_category=query.category,
                result_type="web",
                domain="example.com",
                source_tier="other",
                trusted=False,
            )
        ][:limit]


class FakeAnalyticsModel:
    model = "test-model"

    def __init__(self, evidence_ref="E001") -> None:
        self.evidence_ref = evidence_ref
        self.requests = []

    def generate_json(self, developer_prompt, evidence, schema):
        self.requests.append((developer_prompt, evidence, schema))
        finding = {
            "course_specifics": ["SLMC registration"],
            "finding": "SLMC registration keeps the route to practice clear over the next five years.",
            "evidence_refs": [self.evidence_ref],
            "reasoning_type": "forward_inference",
            "confidence": "medium",
        }
        return {
            "evidence_synthesis": [
                {
                    "theme": "Demand",
                    "key_details": ["SLMC registration"],
                    "takeaway": "Roles exist but entry is competitive.",
                    "agreement": "single_source",
                    "evidence_refs": [self.evidence_ref],
                }
            ],
            "course_introduction": {
                "overview": "You learn to measure and price construction work.",
                "career_paths": [
                    {"role": "Quantity surveyor", "what_you_do": "Prepares BOQs and controls project costs."}
                ],
                "evidence_refs": [self.evidence_ref],
            },
            "future_swot": {
                "strengths": [finding],
                "weaknesses": [],
                "opportunities": [],
                "threats": [],
            },
            "local_vs_overseas": {
                "label": "overseas_stronger",
                "explanation": "Most strong demand found is abroad.",
                "evidence_refs": [self.evidence_ref],
            },
            "further_study": {
                "role": "helpful",
                "explanation": "A masters helps for specialist roles.",
                "evidence_refs": [self.evidence_ref],
            },
            "niche_specialisations": [
                {
                    "area": "whole life carbon assessment",
                    "why_it_matters": "RICS standards are pushing carbon reporting abroad.",
                    "evidence_refs": [self.evidence_ref],
                }
            ],
            "overall_outlook": {
                "label": "positive",
                "summary": "The evidence supports a cautiously positive outlook.",
                "evidence_refs": [self.evidence_ref],
                "confidence": "medium",
            },
            "limitations": ["Future conditions may change."],
        }


class CareerWebResearchTest(unittest.TestCase):
    def test_collects_raw_pages_without_analysis(self) -> None:
        crawler = FakeWebCrawler()
        events = []
        result = CareerWebResearchAgent(crawler).research(
            WebResearchRequest(
                courses=("Medicine",),
                results_per_query=2,
                max_sources_per_course=5,
                content_char_limit=500,
            ),
            on_progress=events.append,
        )

        course = result["course_research"][0]
        self.assertEqual(result["status"], "partial_failure")
        self.assertFalse(result["analytics_performed"])
        self.assertFalse(result["swot_performed"])
        self.assertIn("medical officer", course["occupation_search_terms"])
        self.assertTrue(course["occupation_mapping_found"])
        self.assertEqual(course["course_category"], "medicine")
        self.assertEqual(len(course["documents"]), 5)
        self.assertEqual(len(course["documents"][0]["markdown"]), 500)
        self.assertTrue(course["documents"][0]["content_truncated"])
        self.assertGreater(course["collection"]["category_coverage"]["local_challenges"], 0)
        challenges = next(
            query for query in course["queries"] if query["category"] == "local_challenges"
        )
        self.assertIn("layoffs", challenges["query"])
        self.assertIn("internship shortage", challenges["query"])
        self.assertEqual(crawler.calls, 8)
        event_types = [event["event"] for event in events]
        self.assertEqual(event_types.count("query_started"), 8)
        self.assertEqual(event_types.count("query_completed"), 7)
        self.assertEqual(event_types.count("query_failed"), 1)

    def test_request_normalizes_courses_and_validates_limits(self) -> None:
        request = WebResearchRequest(courses=("IT", " it ", "Medicine"))
        self.assertEqual(request.courses, ("IT", "Medicine"))
        with self.assertRaises(ValueError):
            WebResearchRequest(courses=("IT",), results_per_query=0)

    def test_firecrawl_search_response_becomes_raw_document(self) -> None:
        client = FirecrawlClient(api_key="test-key")
        response = {
            "success": True,
            "data": {
                "web": [
                    {
                        "url": "https://www.bls.gov/ooh/test.htm?utm_source=test",
                        "title": "Employment outlook",
                        "description": "Projection data",
                        "markdown": "# Employment outlook\nProjected growth.",
                    }
                ],
                "news": [
                    {
                        "url": "https://example.com/news",
                        "title": "Hiring slowdown",
                        "description": "Recent hiring evidence",
                        "markdown": "# Hiring slowdown\nRecent evidence.",
                    }
                ],
            },
        }
        with patch.object(client, "_post_json", return_value=response) as post:
            documents = client.search_documents(
                SearchQuery(
                    "global_outlook",
                    "medical officer outlook",
                    ("web", "news"),
                ),
                3,
            )

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].source_tier, "global_official")
        self.assertTrue(documents[0].trusted)
        self.assertEqual(documents[1].result_type, "news")
        self.assertNotIn("utm_source", documents[0].url)
        self.assertEqual(post.call_args.args[0], "/search")
        self.assertEqual(post.call_args.args[1]["scrapeOptions"]["formats"], ["markdown"])
        self.assertEqual(
            post.call_args.args[1]["sources"],
            [{"type": "web"}, {"type": "news"}],
        )

    def test_cli_summary_and_env_loading(self) -> None:
        args = build_parser().parse_args(
            ["--course", "Medicine", "--region", "Sri Lanka"]
        )
        self.assertEqual(args.course, ["Medicine"])

        result = CareerWebResearchAgent(FakeWebCrawler()).research(
            WebResearchRequest(courses=("Medicine",))
        )
        summary = format_answer(result)
        self.assertIn("Medicine (partial failure)", summary)
        self.assertIn("Raw web data only", summary)

        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('FIRECRAWL_API_KEY="test-key"\n')
            with patch.dict("os.environ", {}, clear=True):
                loaded_path = load_environment(env_file)
                self.assertEqual(loaded_path, env_file)
                self.assertEqual(
                    __import__("os").environ["FIRECRAWL_API_KEY"],
                    "test-key",
                )

    def test_future_swot_uses_only_collected_evidence(self) -> None:
        web_result = CareerWebResearchAgent(FakeWebCrawler()).research(
            WebResearchRequest(courses=("Medicine",))
        )
        model = FakeAnalyticsModel()
        events = []
        result = FutureCareerAnalyticsAgent(model).analyze(
            web_result,
            horizon_years=5,
            on_progress=events.append,
        )

        analysis = result["course_analyses"][0]
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(
            analysis["analysis_context"]["expected_entry_year"],
            datetime.now(timezone.utc).year + 5,
        )
        self.assertEqual(
            analysis["future_swot"]["strengths"][0]["evidence_refs"],
            ["E001"],
        )
        self.assertEqual(model.requests[0][1]["region"], "Sri Lanka")
        self.assertIn("untrusted data", model.requests[0][0])
        self.assertEqual(events[-1]["event"], "course_completed")

    def test_future_swot_rejects_unknown_evidence_reference(self) -> None:
        web_result = CareerWebResearchAgent(FakeWebCrawler()).research(
            WebResearchRequest(courses=("Law",))
        )
        result = FutureCareerAnalyticsAgent(
            FakeAnalyticsModel(evidence_ref="UNKNOWN")
        ).analyze(web_result)

        self.assertEqual(result["status"], "failed")
        self.assertIn("unknown evidence", result["course_analyses"][0]["error"])

    def test_openai_client_requests_strict_structured_output(self) -> None:
        expected = FakeAnalyticsModel().generate_json("", {}, {})
        response = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(expected)}
                    ],
                }
            ],
        }
        client = OpenAIResponsesClient(api_key="test-key", model="test-model")
        with patch.object(client, "_post_json", return_value=response) as post:
            result = client.generate_json("instructions", {"evidence": []}, {})

        self.assertEqual(result, expected)
        path, payload = post.call_args.args
        self.assertEqual(path, "/responses")
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["input"][0]["role"], "developer")

class RedditCommunitySignalsTest(unittest.TestCase):
    def test_apify_items_become_untrusted_post_documents(self) -> None:
        client = ApifyRedditClient(api_token="test-token")
        items = [
            {
                "dataType": "post",
                "id": "t3_abc",
                "url": "https://www.reddit.com/r/srilanka/comments/abc/laid_off/?utm_source=x",
                "title": "Laid off after 10 years",
                "body": "Entry-level roles now ask for 3 years of experience.",
                "communityName": "r/srilanka",
                "createdAt": "2026-09-01T10:00:00.000Z",
                "upVotes": 120,
                "numberOfComments": 2,
            },
            {"dataType": "comment", "parentId": "t3_abc", "body": "Low", "upVotes": 1},
            {"dataType": "comment", "parentId": "t3_abc", "body": "Top", "upVotes": 50},
            {"dataType": "post", "id": "t3_nsfw", "url": "https://x", "over18": True},
        ]
        query = SearchQuery(
            "community_signals",
            "a | b",
            ("reddit",),
            ("software engineer Sri Lanka", "Computer Science jobs Sri Lanka"),
        )
        with patch.object(client, "_run_actor", return_value=items) as run:
            documents = client.search_documents(query, 3)

        payload = run.call_args.args[0]
        self.assertEqual(payload["searchTerms"], list(query.variants))
        self.assertEqual(payload["maxPostsCount"], 3)
        self.assertTrue(payload["crawlCommentsPerPost"])
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.source_tier, "community_discussion")
        self.assertFalse(document.trusted)
        self.assertEqual(document.result_type, "reddit")
        self.assertNotIn("utm_source", document.url)
        self.assertIn("anecdotal", document.markdown)
        self.assertLess(document.markdown.index("Top"), document.markdown.index("Low"))

    def test_harshmaur_items_group_replies_and_drop_moderation(self) -> None:
        items = [
            {
                "dataType": "post",
                "id": "t3_p1",
                "postUrl": "https://www.reddit.com/r/srilanka/comments/p1/se_market/",
                "title": "Software Engineering job market",
                "body": "Is it worth it?",
                "communityName": "r/srilanka",
                "createdAt": "2026-10-28T12:02:25.000Z",
                "upVotes": "7",
                "commentsCount": "23",
                "over18": False,
            },
            {
                "dataType": "comment", "postId": "t3_p1", "parentId": "t3_p1",
                "authorName": "AutoModerator", "stickied": True,
                "body": "Serious tag notice", "commentUpVotes": "1",
            },
            {
                "dataType": "comment", "postId": "t3_p1", "parentId": "t1_x",
                "authorName": "someone", "body": "Hard for freshers now",
                "commentUpVotes": "9", "commentCreatedAt": "2026-10-28T13:15:16.000Z",
            },
        ]
        documents = reddit_documents(
            items, SearchQuery("community_signals", "q", ("reddit",)), 5
        )
        self.assertEqual(len(documents), 1)
        markdown = documents[0].markdown
        self.assertIn("23 comments", markdown)
        self.assertIn("(9 upvotes, 2026-10-28) Hard for freshers now", markdown)
        self.assertNotIn("Serious tag notice", markdown)

    def test_reddit_domain_is_classified_but_never_trusted(self) -> None:
        self.assertEqual(classify_domain("www.reddit.com"), ("community_discussion", False))
        self.assertEqual(classify_domain("statistics.gov.lk"), ("local_official", True))

    def test_community_query_routes_to_community_crawler_only(self) -> None:
        web, community = FakeWebCrawler(), FakeWebCrawler()
        result = CareerWebResearchAgent(web, community_crawler=community).research(
            WebResearchRequest(courses=("Computer Science",))
        )
        categories = [q["category"] for q in result["course_research"][0]["queries"]]
        self.assertIn("community_signals", categories)
        self.assertEqual(community.calls, 1)
        self.assertEqual(web.calls, len(categories) - 1)
        self.assertEqual(result["community_source"], "FakeWebCrawler")

    def test_community_query_skipped_without_collector(self) -> None:
        result = CareerWebResearchAgent(FakeWebCrawler()).research(
            WebResearchRequest(courses=("Computer Science",))
        )
        categories = [q["category"] for q in result["course_research"][0]["queries"]]
        self.assertNotIn("community_signals", categories)
        self.assertIsNone(result["community_source"])

    def test_evidence_packet_falls_back_to_snippet_for_unscraped_pages(self) -> None:
        course = {
            "documents": [
                {
                    "url": "https://www.reddit.com/r/srilanka/comments/x/",
                    "title": "Laid off",
                    "description": "I recently faced a layoff.",
                    "markdown": "",
                    "source_tier": "community_discussion",
                }
            ]
        }
        evidence, _ = build_evidence_packet(
            course, max_documents=5, max_content_chars=1_000
        )
        self.assertEqual(len(evidence), 1)
        self.assertIn("Search snippet only", evidence[0]["content"])
        self.assertIn("layoff", evidence[0]["content"])

class SlowCrawler:
    """Blocking crawler that sleeps, to prove searches overlap."""

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def search_documents(self, query, limit):
        time.sleep(self.delay)
        return [
            WebDocument(
                url=f"https://example.com/{query.category}",
                title=query.category, description="d", markdown="m",
                query=query.text, query_category=query.category,
                result_type="web", domain="example.com",
                source_tier="other", trusted=False,
            )
        ]


class TavilyAndConcurrencyTest(unittest.TestCase):
    def test_tavily_maps_structured_filters_to_request(self) -> None:
        client = TavilyClient(api_key="tvly-test", search_depth="advanced")
        response = {
            "results": [
                {
                    "url": "https://www.statistics.gov.lk/report?utm_source=x",
                    "title": "Labour Force Survey",
                    "content": "Short extract",
                    "raw_content": "# Full report",
                    "score": 0.9,
                },
                {"url": "https://example.com/a", "title": "No raw", "content": "Only extract"},
            ]
        }
        query = SearchQuery(
            "local_challenges", "layoffs Sri Lanka", ("web", "news"),
            include_domains=("statistics.gov.lk",), time_range="year", country="Sri Lanka",
        )
        with patch.object(client, "_post_json", return_value=response) as post:
            documents = client.search_documents(query, 3)

        path, payload = post.call_args.args
        self.assertEqual(path, "/search")
        self.assertEqual(payload["topic"], "general")
        self.assertEqual(payload["country"], "sri lanka")
        self.assertEqual(payload["time_range"], "year")
        self.assertEqual(payload["include_domains"], ["statistics.gov.lk"])
        self.assertEqual(payload["include_raw_content"], "markdown")
        self.assertEqual(payload["max_results"], 3)
        self.assertEqual(documents[0].markdown, "# Full report")
        self.assertTrue(documents[0].trusted)
        self.assertNotIn("utm_source", documents[0].url)
        self.assertEqual(documents[1].markdown, "Only extract")

    def test_firecrawl_translates_domains_and_time_range(self) -> None:
        client = FirecrawlClient(api_key="test-key")
        query = SearchQuery(
            "field_sources", "careers", include_domains=("slasscom.lk", "worldbank.org"),
            time_range="year",
        )
        with patch.object(client, "_post_json", return_value={"success": True, "data": []}) as post:
            client.search_documents(query, 3)
        payload = post.call_args.args[1]
        self.assertIn("(site:slasscom.lk OR site:worldbank.org)", payload["query"])
        self.assertEqual(payload["tbs"], "qdr:y")

    def test_planner_uses_structured_filters(self) -> None:
        queries = {q.category: q for q in build_search_queries(profile_for("Computer Science"), "Sri Lanka")}
        self.assertEqual(queries["field_sources"].include_domains, ("slasscom.lk", "worldbank.org"))
        self.assertNotIn("site:", queries["field_sources"].text)
        self.assertEqual(queries["local_challenges"].time_range, "year")
        self.assertIn("working abroad", queries["international_pathways"].text)
        self.assertIsNone(queries["international_pathways"].country)
        self.assertIn("postgraduate", queries["further_study"].text)
        self.assertIn("masters abroad", queries["community_signals"].text)
        self.assertEqual(classify_domain("pgim.cmb.ac.lk"), ("local_official", True))
        self.assertEqual(queries["local_live_jobs"].country, "Sri Lanka")
        self.assertIsNone(queries["global_outlook"].country)

    def test_social_media_pages_are_dropped(self) -> None:
        from campusyamu.agents.career_trends.web_results import select_documents

        def doc(domain):
            return WebDocument(
                url=f"https://{domain}/p", title=domain, description="", markdown="m",
                query="q", query_category="further_study", result_type="web",
                domain=domain, source_tier="other", trusted=False,
            )

        kept = select_documents([doc("www.instagram.com"), doc("m.facebook.com"), doc("ugc.ac.lk")], 10)
        self.assertEqual([d.domain for d in kept], ["ugc.ac.lk"])
        client = TavilyClient(api_key="tvly-test")
        with patch.object(client, "_post_json", return_value={"results": []}) as post:
            client.search_documents(SearchQuery("further_study", "q"), 3)
        self.assertIn("instagram.com", post.call_args.args[1]["exclude_domains"])

    def test_provider_selection(self) -> None:
        with patch.dict("os.environ", {"TAVILY_API_KEY": "k"}, clear=True):
            self.assertEqual(web_provider_name(), "tavily")
            self.assertEqual(web_provider_name("firecrawl"), "firecrawl")
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "k"}, clear=True):
            self.assertEqual(web_provider_name(), "firecrawl")
        with patch.dict("os.environ", {"SEARCH_PROVIDER": "bing"}, clear=True):
            with self.assertRaises(ValueError):
                web_provider_name()

    def test_web_and_reddit_searches_run_concurrently(self) -> None:
        agent = CareerWebResearchAgent(
            SlowCrawler(0.3), community_crawler=SlowCrawler(0.3)
        )
        started = time.monotonic()
        result = agent.research(WebResearchRequest(courses=("Computer Science",)))
        elapsed = time.monotonic() - started
        query_count = len(result["course_research"][0]["queries"])
        self.assertEqual(query_count, 9)
        # Sequential would take 9 x 0.3s = 2.7s; concurrent is ~0.3s.
        self.assertLess(elapsed, 0.9)
        self.assertEqual(result["status"], "success")

class PipelineTest(unittest.TestCase):
    def test_course_in_swot_out(self) -> None:
        model = FakeAnalyticsModel()
        pipeline = CareerTrendsPipeline(
            CareerWebResearchAgent(FakeWebCrawler(), community_crawler=FakeWebCrawler()),
            FutureCareerAnalyticsAgent(model),
        )
        result = pipeline.run(WebResearchRequest(courses=("Computer Science",)), horizon_years=4)

        # local_market fails in the fake crawler, so collection is partial.
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["input"]["horizon_years"], 4)
        analysis = result["course_analyses"][0]
        self.assertEqual(analysis["status"], "success")
        self.assertEqual(analysis["analysis_context"]["horizon_years"], 4)
        self.assertEqual(result["collection"][0]["failed_searches"][0]["category"], "local_market")
        categories = {item["query_category"] for item in model.requests[0][1]["evidence"]}
        self.assertIn("community_signals", categories)
        text = pipeline_format_answer(result)
        self.assertIn("Computer Science sources:", text)
        self.assertIn("Where the opportunities are: overseas stronger", text)
        self.assertIn("Further study: helpful", text)
        self.assertIn("About this degree: You learn to measure", text)
        self.assertIn("    - Quantity surveyor: Prepares BOQs", text)
        self.assertLess(text.index("About this degree"), text.index("Overall:"))
        self.assertIn("[E001]", text)

    def test_invalid_horizon_fails_before_collection(self) -> None:
        crawler = FakeWebCrawler()
        pipeline = CareerTrendsPipeline(
            CareerWebResearchAgent(crawler), FutureCareerAnalyticsAgent(FakeAnalyticsModel())
        )
        with self.assertRaises(ValueError):
            pipeline.run(WebResearchRequest(courses=("Law",)), horizon_years=9)
        self.assertEqual(crawler.calls, 0)

    def test_high_confidence_needs_a_trusted_source(self) -> None:
        analysis = {
            "future_swot": {
                "strengths": [
                    {"evidence_refs": ["E001", "E002"], "confidence": "high"},
                    {"evidence_refs": ["E003"], "confidence": "high"},
                ],
                "weaknesses": [{"evidence_refs": ["E001"], "confidence": "low"}],
                "opportunities": [],
                "threats": [],
            },
            "overall_outlook": {"evidence_refs": ["E001"], "confidence": "high"},
        }
        lowered = cap_unverified_confidence(analysis, trusted_ids={"E003"})
        self.assertEqual(lowered, 2)
        strengths = analysis["future_swot"]["strengths"]
        self.assertEqual(strengths[0]["confidence"], "medium")
        self.assertEqual(strengths[1]["confidence"], "high")
        self.assertEqual(analysis["future_swot"]["weaknesses"][0]["confidence"], "low")
        self.assertEqual(analysis["overall_outlook"]["confidence"], "medium")

    def test_evidence_budget_is_shared_fairly(self) -> None:
        self.assertEqual(_fair_shares([100, 8000, 8000], 3000), [100, 1450, 1450])
        self.assertEqual(sum(_fair_shares([8000] * 15, 60000)), 60000)
        course = {"documents": [
            {"url": f"https://e.com/{i}", "markdown": "x" * 8000} for i in range(15)
        ]}
        evidence, _ = build_evidence_packet(course, max_documents=50, max_content_chars=60000)
        self.assertEqual(len(evidence), 15)
        self.assertEqual({len(item["content"]) for item in evidence}, {4000})

CAREER_PAGE = (
    "Graduates can work in banking, investment, insurance, risk management, "
    "actuarial science or data science roles, for example as quantitative analysts."
)


TRENDS_PAGE = (
    "The future of the profession: whole life carbon assessment is a growing "
    "specialisation, and contract administration skills are increasingly in demand."
)


class CareerPageCrawler:
    def __init__(self) -> None:
        self.calls = []

    def search_documents(self, query, limit):
        self.calls.append(query)
        if query.category == "emerging_specialisations" and query.text.startswith("future of the"):
            return [
                WebDocument(
                    url="https://body.example/future", title="Future of the profession",
                    description="", markdown=TRENDS_PAGE, query=query.text,
                    query_category="emerging_specialisations", result_type="web",
                    domain="body.example", source_tier="other", trusted=False,
                )
            ]
        if query.category == "career_paths":
            return [
                WebDocument(
                    url="https://uni.example/fm-careers", title="FM careers",
                    description="", markdown=CAREER_PAGE, query=query.text,
                    query_category="career_paths", result_type="web",
                    domain="uni.example", source_tier="other", trusted=False,
                )
            ]
        return FakeWebCrawler().search_documents(query, limit)


class TitleModel:
    model = "test-model"

    def __init__(self, titles, areas=()) -> None:
        self.titles = titles
        self.areas = list(areas)

    def generate_json(self, prompt, payload, schema):
        return {"occupations": self.titles, "emerging_areas": self.areas}


class CareerDiscoveryTest(unittest.TestCase):
    def test_titles_must_be_grounded_in_page_text(self) -> None:
        titles = grounded_titles(
            ["Risk Analyst", "Actuarial Analyst", "Quantitative Analyst",
             "Banking Officer", "Petroleum Engineer", "Analyst", "Data Scientist"],
            CAREER_PAGE,
        )
        self.assertEqual(
            titles,
            ("risk analyst", "actuarial analyst", "quantitative analyst",
             "banking officer", "data scientist"),
        )

    def test_career_passages_skip_page_boilerplate(self) -> None:
        from campusyamu.agents.career_trends.career_discovery import career_passages

        page = "\n".join(["Home", "Apply now", "Fees and scholarships"] * 200 + [
            "Entry requirements: A/L Maths",
            "Career opportunities",
            "Graduates work as actuarial analysts and risk analysts.",
            "Contact us",
        ])
        passage = career_passages(page, 500)
        self.assertIn("actuarial analysts", passage)
        self.assertNotIn("Apply now", passage)

    def test_discovered_titles_lead_and_taxonomy_fills(self) -> None:
        from campusyamu.agents.career_trends.course_taxonomy import profile_for

        mapped = merge_profile(profile_for("Banking and Finance"), ("risk analyst", "accountant"))
        self.assertEqual(mapped.focus_areas[:3], ("risk analyst", "accountant", "auditor"))
        self.assertEqual(len(set(t.casefold() for t in mapped.focus_areas)), len(mapped.focus_areas))
        unmapped = merge_profile(profile_for("Financial Mathematics"), ("risk analyst",))
        self.assertEqual(unmapped.focus_areas, ("risk analyst",))

    def test_unmapped_course_searches_discovered_jobs(self) -> None:
        crawler = CareerPageCrawler()
        with TemporaryDirectory() as directory:
            discovery = CareerDiscovery(
                crawler, TitleModel(["Risk Analyst", "Actuarial Analyst", "Made Up Job"]),
                cache_path=Path(directory) / "cache.json",
            )
            result = CareerWebResearchAgent(crawler, career_discovery=discovery).research(
                WebResearchRequest(courses=("Financial Mathematics",))
            )
            course = result["course_research"][0]
            self.assertEqual(course["career_discovery"]["status"], "discovered")
            self.assertEqual(course["occupation_search_terms"], ["risk analyst", "actuarial analyst"])
            jobs = next(q for q in course["queries"] if q["category"] == "local_live_jobs")
            self.assertIn('"risk analyst"', jobs["query"])
            self.assertIn("career_paths", course["collection"]["category_coverage"])

            # Second run reads the cache: no new discovery search.
            searches_before = sum(q.category == "career_paths" for q in crawler.calls)
            again = CareerWebResearchAgent(crawler, career_discovery=discovery).research(
                WebResearchRequest(courses=("Financial Mathematics",))
            )
            self.assertEqual(again["course_research"][0]["career_discovery"]["status"], "cached")
            self.assertEqual(
                sum(q.category == "career_paths" for q in crawler.calls), searches_before
            )

    def test_emerging_areas_are_discovered_and_searched(self) -> None:
        crawler = CareerPageCrawler()
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            # An entry saved before emerging areas existed must be refreshed.
            cache.write_text(json.dumps({"financial mathematics::sri lanka": {
                "saved_at": time.time(), "titles": ["risk analyst"], "documents": [],
            }}))
            discovery = CareerDiscovery(
                crawler,
                TitleModel(
                    ["Risk Analyst"],
                    ["Whole Life Carbon Assessment", "Contract Administration", "Quantum Teleportation"],
                ),
                cache_path=cache,
            )
            result = CareerWebResearchAgent(crawler, career_discovery=discovery).research(
                WebResearchRequest(courses=("Financial Mathematics",))
            )
        course = result["course_research"][0]
        self.assertEqual(course["career_discovery"]["status"], "discovered")
        self.assertEqual(
            course["emerging_areas"],
            ["whole life carbon assessment", "contract administration"],
        )
        targeted = next(
            q for q in course["queries"] if q["category"] == "emerging_specialisations"
        )
        self.assertIn('"whole life carbon assessment"', targeted["query"])
        self.assertIn("emerging_specialisations", course["collection"]["category_coverage"])

    def test_planner_asks_about_emerging_areas_without_discovery(self) -> None:
        queries = {q.category: q for q in build_search_queries(profile_for("Quantity Surveying"), "Sri Lanka")}
        emerging = queries["emerging_specialisations"]
        self.assertIn("emerging specialisations", emerging.text)
        self.assertIsNone(emerging.country)

    def test_failed_discovery_falls_back_to_taxonomy(self) -> None:
        crawler = CareerPageCrawler()
        discovery = CareerDiscovery(crawler, TitleModel(["Astronaut"]), cache_path=None)
        result = CareerWebResearchAgent(crawler, career_discovery=discovery).research(
            WebResearchRequest(courses=("Computer Science",))
        )
        course = result["course_research"][0]
        self.assertEqual(course["career_discovery"]["status"], "failed")
        self.assertIn("software engineer", course["occupation_search_terms"])
        self.assertIn("career_paths", [f["category"] for f in course["failures"]])


if __name__ == "__main__":
    unittest.main()
