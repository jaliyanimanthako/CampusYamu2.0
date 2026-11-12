from __future__ import annotations

import json
import unittest

from campusyamu.agents.career_trends.harness import ModelTurn, Tool, ToolCall, ToolRegistry
from campusyamu.agents.career_trends.harness.model import parse_turn
from campusyamu.agents.career_trends.models import WebDocument
from campusyamu.agents.career_trends.research_harness import ResearchHarness, _parse_answer


PAGES = {
    "embodied carbon": "Embodied carbon assessment is a growing specialism for quantity surveyors.",
    "contract administration": "Firms report rising demand for contract administration under FIDIC.",
    "construction law": "Construction law and adjudication skills are scarce among surveyors.",
    "technology": "Technology and sustainable construction practices are changing the field.",
}


class TopicCrawler:
    """Returns one page per known topic in the query."""

    def __init__(self) -> None:
        self.queries = []

    def search_documents(self, query, limit):
        self.queries.append(query)
        return [
            WebDocument(
                url=f"https://body.example/{topic.replace(' ', '-')}",
                title=topic.title(),
                description="",
                markdown=text,
                query=query.text,
                query_category=query.category,
                result_type="web",
                domain="body.example",
                source_tier="other",
                trusted=False,
            )
            for topic, text in PAGES.items()
            if topic in query.text.casefold()
        ][:limit]


class ScriptedModel:
    model = "fake-mini"

    def __init__(self, turns) -> None:
        self.turns = list(turns)
        self.summary_calls = 0
        self.context_sizes = []

    def step(self, instructions, items, tools):
        if not tools:  # compaction request
            self.summary_calls += 1
            return ModelTurn("Found embodied carbon (S004). Still need a second area.")
        self.context_sizes.append(len(items))
        return self.turns.pop(0)


def search(query, call_id, category="emerging_specialisations"):
    arguments = json.dumps(
        {"query": query, "category": category, "local": False, "recent_only": False}
    )
    return ModelTurn(calls=[ToolCall(call_id, "web_search", arguments)])


def seed_course():
    categories = (
        "local_live_jobs", "local_market", "local_challenges", "global_outlook",
        "international_pathways", "further_study",
    )
    documents = [
        {
            "url": f"https://seed.example/{index}",
            "title": f"Seed {category}",
            "description": "",
            "markdown": "Quantity surveyor vacancies and market notes.",
            "query_category": category,
            "domain": "seed.example",
            "trusted": index < 3,
            "source_tier": "local_official" if index < 3 else "other",
        }
        for index, category in enumerate(categories)
    ]
    return {
        "course": "Quantity Surveying",
        "status": "success",
        "queries": [{"category": "local_market", "query": "quantity surveying market"}],
        "occupation_search_terms": ["quantity surveyor"],
        "emerging_areas": [],
        "documents": documents,
        "collection": {
            "discovered": 6,
            "retained_after_deduplication": 6,
            "trusted_sources": 3,
            "category_coverage": {c: 1 for c in categories},
        },
    }


def web_result(course):
    return {
        "input": {"region": "Sri Lanka", "content_char_limit": 8000},
        "course_research": [course],
    }


class ResearchHarnessTest(unittest.TestCase):
    def test_loop_searches_compacts_and_only_accepts_verified_answers(self) -> None:
        # Seed sources are S001-S006, so the agent's finds are S007 and S008.
        model = ScriptedModel(
            [
                search("embodied carbon quantity surveying demand", "c1"),
                search("Embodied  carbon quantity surveying demand", "c2"),  # duplicate
                # Premature answer: one invented area and one too few verified.
                ModelTurn(
                    "NICHE AREAS:\n"
                    "- Embodied carbon assessment: growing abroad [S007]\n"
                    "- Quantum surveying: made up [S007]\n"
                    "- Sustainable construction practices: broad [S007]\n"
                    "GAPS:\n- none"
                ),
                ModelTurn(calls=[
                    *search("contract administration skills quantity surveyors", "c3").calls,
                    *search("construction law adjudication surveyors digital", "c4").calls,
                ]),
                ModelTurn(
                    "NICHE AREAS:\n"
                    "- Embodied carbon assessment: clients want carbon figures [S007]\n"
                    "- **Contract administration**: rising FIDIC work [S008]\n"
                    "- Construction law: adjudication skills are scarce [S009]\n"
                    "GAPS:\n- no Sri Lankan carbon jobs found"
                ),
            ]
        )
        events = []
        course = seed_course()
        ResearchHarness(TopicCrawler(), model, compact_every=3).enrich(
            web_result(course), events.append
        )

        agent = course["agent_research"]
        self.assertEqual(agent["status"], "satisfied")
        self.assertEqual(agent["iterations"], 5)
        self.assertEqual(agent["compactions"], 1)
        self.assertEqual(model.summary_calls, 1)
        # After compaction the model sees two messages, not the old transcript.
        self.assertEqual(model.context_sizes[3], 2)
        self.assertEqual(
            [area["area"] for area in agent["niche_areas"]],
            ["Embodied carbon assessment", "Contract administration", "Construction law"],
        )
        self.assertEqual(
            agent["niche_areas"][0]["source_urls"], ["https://body.example/embodied-carbon"]
        )
        self.assertEqual(agent["agent_reported_gaps"], ["no Sri Lankan carbon jobs found"])
        rejections = " ".join(agent["guardrail_rejections"])
        self.assertIn("already run", rejections)
        self.assertIn("'Quantum surveying' is not named", rejections)
        self.assertIn("1 verified niche areas", rejections)
        self.assertIn("'Sustainable construction practices' is too broad", rejections)
        self.assertIn("not searched for change driven by law", rejections)
        self.assertIn("not searched for change driven by technology", rejections)
        # The finds join the evidence the SWOT will read.
        self.assertEqual(agent["sources_added"], 3)
        self.assertEqual(len(course["documents"]), 9)
        self.assertEqual(course["collection"]["category_coverage"]["emerging_specialisations"], 3)
        kinds = [event["event"] for event in events]
        self.assertIn("agent_compacted", kinds)
        self.assertEqual(kinds.count("agent_search"), 3)

    def test_unfillable_gaps_are_reported_not_hidden(self) -> None:
        model = ScriptedModel([ModelTurn("NICHE AREAS:\nGAPS:\n- nothing found")])
        course = seed_course()
        ResearchHarness(TopicCrawler(), model, max_searches=0).enrich(web_result(course))
        agent = course["agent_research"]
        # No budget means nothing is blocking, but the result is not "satisfied".
        self.assertEqual(agent["status"], "partial")
        self.assertTrue(any("emerging" in gap for gap in agent["unfilled_gaps"]))
        self.assertTrue(any("niche" in gap for gap in agent["unfilled_gaps"]))

    def test_loop_stops_at_the_iteration_limit(self) -> None:
        model = ScriptedModel([ModelTurn("I am done.")] * 3)
        course = seed_course()
        ResearchHarness(TopicCrawler(), model, max_iterations=3).enrich(web_result(course))
        agent = course["agent_research"]
        self.assertEqual(agent["status"], "stopped_at_limit")
        self.assertEqual(agent["niche_areas"], [])
        self.assertIn("required format", " ".join(agent["guardrail_rejections"]))

    def test_extra_calls_in_one_turn_are_refused(self) -> None:
        many = ModelTurn(calls=[
            *search("embodied carbon surveyors", "a").calls,
            *search("contract administration surveyors", "b").calls,
            *search("construction law surveyors", "c").calls,
        ])
        model = ScriptedModel([many, ModelTurn("NICHE AREAS:\nGAPS:\n- none")])
        course = seed_course()
        ResearchHarness(TopicCrawler(), model, max_iterations=2, max_calls_per_turn=2).enrich(
            web_result(course)
        )
        agent = course["agent_research"]
        self.assertEqual(len(agent["searches"]), 2)
        self.assertIn("At most 2 tool calls per turn", " ".join(agent["guardrail_rejections"]))

    def test_model_failure_leaves_the_evidence_untouched(self) -> None:
        class Broken:
            model = "fake"

            def step(self, *args):
                raise RuntimeError("rate limited")

        course = seed_course()
        ResearchHarness(TopicCrawler(), Broken()).enrich(web_result(course))
        self.assertEqual(course["agent_research"]["status"], "failed")
        self.assertEqual(len(course["documents"]), 6)


class HarnessPartsTest(unittest.TestCase):
    def test_registry_returns_errors_to_the_model(self) -> None:
        def boom(args):
            raise RuntimeError("down")

        registry = ToolRegistry(
            (Tool("t", "test", {"type": "object", "required": ["q"]}, boom),)
        )
        self.assertIn("Unknown tool", registry.execute("x", "{}"))
        self.assertIn("not valid JSON", registry.execute("t", "{"))
        self.assertIn("Missing arguments: q", registry.execute("t", "{}"))
        self.assertIn("t failed: down", registry.execute("t", '{"q": 1}'))
        self.assertEqual(registry.schemas()[0]["strict"], True)

    def test_parse_openai_turn(self) -> None:
        turn = parse_turn(
            {
                "output": [
                    {"type": "function_call", "call_id": "a", "name": "web_search", "arguments": "{}"},
                    {"type": "message", "content": [{"type": "output_text", "text": "hi"}]},
                ]
            }
        )
        self.assertEqual(turn.calls[0].call_id, "a")
        self.assertEqual(turn.text, "hi")

    def test_parse_answer_format(self) -> None:
        niche, gaps = _parse_answer(
            "Here you go.\n**NICHE AREAS:**\n- Carbon: why [S001, S002]\nGAPS:\n- pay data"
        )
        self.assertEqual(niche, [("Carbon", "why", ["S001", "S002"])])
        self.assertEqual(gaps, ["pay data"])
        self.assertEqual(_parse_answer("no format"), (None, []))


if __name__ == "__main__":
    unittest.main()
