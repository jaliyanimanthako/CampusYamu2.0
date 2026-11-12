from __future__ import annotations

import json
import unittest

from campusyamu.agents.course_finder.finder import CourseFinder
from campusyamu.agents.ranking.feedback import FeedbackWriter, LLMFeedback, TemplateFeedback
from campusyamu.agents.ranking.sensitivity import analyse
from campusyamu.pipeline.graph import build_pipeline, run_pipeline

STUDENT = dict(stream="Physical Science", al=["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
               cgt=40, admission_district="Kandy", home="Gangawata Korale",
               ol=["Science:B", "English:B", "Maths:A"], z_score=1.56,
               preferences="AI, engineering, computers, software")
CONTEXT = {"stream": "Physical Science", "z_score": 1.56, "interests": "x"}


def row(code, band, cutoff, pref, car):
    return {"uni_code": code, "course_name": f"Course {code}", "university": "U", "band": band,
            "latest_cutoff": cutoff, "preference_score": pref, "car_min": car, "expected_margin": 0.0}


# NEAR: close but low cut-off; HIGH: far, high cut-off; LIKE: best interest; MID: average on all
ROWS = [row("NEAR", "strong", 1.0, 6.0, 10), row("HIGH", "unlikely", 2.2, 6.0, 400),
        row("LIKE", "competitive", 1.4, 9.0, 200), row("MID", "reach", 1.5, 7.0, 150)]


class SensitivityTests(unittest.TestCase):
    def test_profiles_move_courses_the_expected_way(self) -> None:
        a = analyse(ROWS, limit=3)
        c = {x["uni_code"]: x for x in a["courses"]}
        self.assertEqual(sum(x["in_list"] for x in a["courses"]), 3)
        self.assertEqual(c["NEAR"]["strength"], "distance")
        self.assertEqual(c["HIGH"]["strength"], "cutoff")
        self.assertEqual(c["LIKE"]["strength"], "interest")
        # leaning on a factor never makes the course strongest in it rank worse
        self.assertLessEqual(c["NEAR"]["profile_ranks"]["closer_to_home"], c["NEAR"]["balanced_rank"])
        self.assertLessEqual(c["HIGH"]["profile_ranks"]["selectivity_first"], c["HIGH"]["balanced_rank"])
        self.assertLessEqual(c["LIKE"]["profile_ranks"]["interest_first"], c["LIKE"]["balanced_rank"])
        for x in a["courses"]:
            self.assertEqual(x["moves"]["interest_first"],
                             x["balanced_rank"] - x["profile_ranks"]["interest_first"])

    def test_outside_courses_that_enter_are_included(self) -> None:
        a = analyse(ROWS, limit=3)
        outside = [x for x in a["courses"] if not x["in_list"]]
        for x in outside:
            self.assertTrue(any(r <= 3 for r in x["profile_ranks"].values()))
            self.assertTrue(any(x["uni_code"] in codes for codes in a["risers"].values()))

    def test_near_ties_are_grouped(self) -> None:
        tied = [row(f"T{i}", "strong", 1.0, 5.0 - i * 0.05, 10) for i in range(4)] + [row("GAP", "strong", 1.0, 3.0, 10)]
        a = analyse(tied, limit=5)
        self.assertEqual([cc["uni_codes"] for cc in a["close_calls"]], [["T0", "T1", "T2", "T3"]])
        self.assertEqual(a["close_calls"][0]["ranks"], [1, 4])


class FeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analysis = analyse(ROWS, limit=3)

    def test_template_gives_every_course_a_note(self) -> None:
        fb = TemplateFeedback().write(self.analysis, CONTEXT)
        self.assertEqual(set(fb["course_notes"]), {c["uni_code"] for c in self.analysis["courses"]})
        self.assertIn("close to home", fb["course_notes"]["NEAR"]["note"])
        self.assertEqual([p["profile"] for p in fb["priorities"]],
                         ["closer_to_home", "interest_first", "selectivity_first"])
        self.assertTrue(fb["summary"])

    def test_llm_payload_is_strict_and_limited_to_known_courses(self) -> None:
        llm = LLMFeedback(model="test", api_key="k")
        payload = llm.request_payload(self.analysis, CONTEXT)
        fmt = payload["text"]["format"]
        self.assertTrue(fmt["strict"])
        enum = fmt["schema"]["properties"]["course_notes"]["items"]["properties"]["uni_code"]["enum"]
        self.assertEqual(set(enum), {c["uni_code"] for c in self.analysis["courses"]})
        sent = json.loads(payload["input"][1]["content"])
        self.assertEqual(sent["courses"][0]["profile_ranks"], self.analysis["courses"][0]["profile_ranks"])
        self.assertFalse(payload["store"])

    def test_llm_answer_is_validated_and_gaps_filled(self) -> None:
        llm = LLMFeedback(model="test", api_key="k")
        first = self.analysis["courses"][0]["uni_code"]
        raw = {"summary": "  A short   summary. ",
               "course_notes": [{"uni_code": first, "note": "Good pick."}, {"uni_code": "FAKE", "note": "x"}],
               "priorities": [{"profile": "closer_to_home", "advice": "Stay near."},
                              {"profile": "made_up", "advice": "y"}],
               "close_calls": [], "cautions": ["Watch out."]}
        fb = llm.parse(raw, self.analysis, CONTEXT)
        self.assertEqual(fb["summary"], "A short summary.")
        self.assertEqual(fb["course_notes"][first], {"note": "Good pick.", "source": "llm"})
        self.assertNotIn("FAKE", fb["course_notes"])
        others = [c for c in fb["course_notes"].values() if c["source"] == "template"]
        self.assertEqual(len(others), len(self.analysis["courses"]) - 1)
        self.assertEqual(fb["priorities"][0]["advice"], "Stay near.")
        self.assertEqual(fb["priorities"][1]["source"], "template")
        self.assertIn("missing from the LLM answer", fb["notes"][0])

    def test_failed_call_falls_back_to_template(self) -> None:
        writer = FeedbackWriter(use_llm=False)
        writer.llm = LLMFeedback(model="test", api_key="k")

        def boom(_payload):
            raise RuntimeError("offline")
        writer.llm._call = boom
        fb = writer.write(self.analysis, CONTEXT)
        self.assertEqual(fb["method"], "template")
        self.assertIn("offline", fb["notes"][-1])
        self.assertEqual(FeedbackWriter(use_llm=False).write({"courses": []}, CONTEXT)["method"], "none")


class PipelineFeedbackTests(unittest.TestCase):
    def test_order3_has_analysis_and_a_note_per_course(self) -> None:
        finder = CourseFinder()
        try:
            app = build_pipeline(finder, use_llm=False)
            report = run_pipeline(STUDENT, app)["report"]
        finally:
            finder.close()
        order3 = report["rankings"]["distance"]
        listed = [s["uni_code"] for s in order3["suggestions"]]
        analysed = [c["uni_code"] for c in order3["analysis"]["courses"] if c["in_list"]]
        self.assertEqual(listed, analysed)                                       # same order as shown
        self.assertTrue(set(listed) <= set(order3["feedback"]["course_notes"]))
        self.assertEqual(order3["feedback"]["method"], "template")
        for s in order3["suggestions"]:
            self.assertAlmostEqual(sum(s["parts"].values()), s["combined_score"], delta=0.02)
        self.assertIn("explain_rankings", set(app.get_graph().nodes))


if __name__ == "__main__":
    unittest.main()
