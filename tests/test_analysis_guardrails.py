from __future__ import annotations

import copy
import unittest

from career_trends_agent.analysis_guardrails import (
    drop_items,
    offending_sentences,
    specificity_problems,
    strip_offending,
)
from career_trends_agent.future_analytics import FutureCareerAnalyticsAgent


EVIDENCE = [
    {
        "evidence_id": "E001",
        "title": "Quantity Surveyors - Mynott Bowers",
        "content": "Mynott Bowers is hiring junior quantity surveyors in Matara. CostX skills preferred.",
        "trusted": False,
    },
    {
        "evidence_id": "E002",
        "title": "Employment outlook",
        "content": "SCSI expects strong demand for surveyors in Ireland through 2029.",
        "trusted": True,
    },
]


def finding(text, specifics, refs=("E001",)):
    return {
        "course_specifics": list(specifics),
        "finding": text,
        "evidence_refs": list(refs),
        "reasoning_type": "direct_evidence",
        "confidence": "medium",
    }


def answer(strengths, summary="Right now CostX skills matter locally, and SCSI expects Ireland to need surveyors."):
    return {
        "evidence_synthesis": [{"theme": "t", "key_details": [], "takeaway": "t",
                                "agreement": "single_source", "evidence_refs": ["E001"]}],
        "course_introduction": {"overview": "o", "career_paths": [], "evidence_refs": ["E001"]},
        "future_swot": {"strengths": strengths, "weaknesses": [], "opportunities": [], "threats": []},
        "local_vs_overseas": {"label": "unclear", "explanation": "e", "evidence_refs": ["E002"]},
        "further_study": {"role": "helpful", "explanation": "e", "evidence_refs": ["E002"]},
        "niche_specialisations": [],
        "overall_outlook": {"label": "mixed", "summary": summary,
                            "evidence_refs": ["E001"], "confidence": "medium"},
        "limitations": [],
    }


SPECIFIC = finding("Right now, junior QS openings in Matara ask for CostX skills.", ["CostX", "Matara"])
GENERIC = finding("There is high demand, ensuring stable job prospects.", ["high demand"])
UNSUPPORTED = finding("RICS membership is what employers want.", ["RICS"])


class SpecificityTest(unittest.TestCase):
    def check(self, item):
        return specificity_problems(answer([item]), EVIDENCE, "Quantity Surveying", "Sri Lanka")

    def test_specific_finding_passes(self) -> None:
        self.assertEqual(self.check(SPECIFIC), [])

    def test_generic_finding_fails(self) -> None:
        self.assertIn("is generic", self.check(GENERIC)[0].message)

    def test_name_missing_from_cited_source_fails(self) -> None:
        self.assertIn("is generic", self.check(UNSUPPORTED)[0].message)

    def test_finding_must_use_its_specifics(self) -> None:
        item = finding("Entry-level openings exist.", ["CostX"])
        self.assertIn("does not mention", self.check(item)[0].message)

    def test_vague_summary_fails_but_is_not_dropped(self) -> None:
        problems = specificity_problems(
            answer([SPECIFIC], summary="The outlook is positive overall."),
            EVIDENCE, "Quantity Surveying", "Sri Lanka",
        )
        self.assertEqual(len(problems), 1)
        self.assertIsNone(problems[0].path)

    def test_drop_removes_only_failing_items(self) -> None:
        value = answer([SPECIFIC, GENERIC])
        problems = specificity_problems(value, EVIDENCE, "Quantity Surveying", "Sri Lanka")
        self.assertEqual(drop_items(value, problems), 1)
        self.assertEqual(value["future_swot"]["strengths"], [SPECIFIC])


class AdviceAndAdvertTest(unittest.TestCase):
    def test_detects_advice_and_individual_adverts(self) -> None:
        for sentence in (
            "Practise CostX during your degree.",
            "You should join IQSSL early.",
            "Consider an internship with a contractor.",
            "Mynott Bowers has advertised junior roles in Matara.",
            "Apply before the March deadline.",
        ):
            self.assertEqual(offending_sentences(sentence), [sentence], sentence)
        for sentence in (
            "Right now, junior QS openings in Matara ask for CostX skills.",
            "IQSSL membership is what employers look for when they promote.",
            "Current hiring is a snapshot and may look different by 2031.",
        ):
            self.assertEqual(offending_sentences(sentence), [], sentence)

    def test_advice_is_flagged_for_revision(self) -> None:
        item = finding(
            "Right now, junior QS openings in Matara ask for CostX skills. "
            "Practise CostX during your degree.",
            ["CostX", "Matara"],
        )
        problems = specificity_problems(answer([item]), EVIDENCE, "Quantity Surveying", "Sri Lanka")
        self.assertEqual(len(problems), 1)
        self.assertIn("gives advice", problems[0].message)

    def test_surviving_advice_sentences_are_cut(self) -> None:
        value = answer(
            [
                finding(
                    "Right now, junior QS openings in Matara ask for CostX skills. "
                    "Practise CostX during your degree.",
                    ["CostX", "Matara"],
                ),
                finding("Mynott Bowers has advertised junior roles.", ["Mynott Bowers"]),
            ],
            summary="SCSI expects Ireland to need surveyors. You should learn CostX.",
        )
        self.assertEqual(strip_offending(value), 3)
        self.assertEqual(
            value["future_swot"]["strengths"][0]["finding"],
            "Right now, junior QS openings in Matara ask for CostX skills.",
        )
        self.assertEqual(value["future_swot"]["strengths"][1]["finding"], "")
        self.assertEqual(value["overall_outlook"]["summary"], "SCSI expects Ireland to need surveyors.")
        # The emptied finding is then dropped.
        problems = specificity_problems(value, EVIDENCE, "Quantity Surveying", "Sri Lanka")
        drop_items(value, problems)
        self.assertEqual(len(value["future_swot"]["strengths"]), 1)


class ScriptedSwotModel:
    model = "fake-mini"

    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.requests = []

    def generate_json(self, prompt, payload, schema):
        self.requests.append((prompt, payload))
        return copy.deepcopy(self.answers.pop(0))


def course():
    return {
        "course": "Quantity Surveying",
        "documents": [
            {"url": "https://mb.example", "title": EVIDENCE[0]["title"],
             "markdown": EVIDENCE[0]["content"], "trusted": False},
            {"url": "https://scsi.example", "title": EVIDENCE[1]["title"],
             "markdown": EVIDENCE[1]["content"], "trusted": True},
        ],
    }


class RevisionTest(unittest.TestCase):
    def run_with(self, model):
        web_result = {"input": {"region": "Sri Lanka"}, "course_research": [course()]}
        return FutureCareerAnalyticsAgent(model).analyze(web_result)["course_analyses"][0]

    def test_generic_answer_is_sent_back_and_fixed(self) -> None:
        model = ScriptedSwotModel(answer([GENERIC]), answer([SPECIFIC]))
        result = self.run_with(model)
        self.assertEqual(len(model.requests), 2)
        self.assertIn("## Revision", model.requests[1][0])
        self.assertIn("is generic", model.requests[1][1]["problems"][0])
        self.assertEqual(result["future_swot"]["strengths"], [SPECIFIC])
        self.assertTrue(result["analysis_context"]["revised"])
        self.assertEqual(result["analysis_context"]["generic_items_dropped"], 0)

    def test_still_generic_after_revision_is_dropped(self) -> None:
        model = ScriptedSwotModel(answer([GENERIC, SPECIFIC]), answer([GENERIC, SPECIFIC]))
        result = self.run_with(model)
        self.assertEqual(result["future_swot"]["strengths"], [SPECIFIC])
        self.assertEqual(result["analysis_context"]["generic_items_dropped"], 1)

    def test_specific_answer_needs_one_call(self) -> None:
        model = ScriptedSwotModel(answer([SPECIFIC]))
        self.run_with(model)
        self.assertEqual(len(model.requests), 1)


if __name__ == "__main__":
    unittest.main()
