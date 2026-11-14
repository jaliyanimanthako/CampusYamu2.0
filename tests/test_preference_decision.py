"""Gemini Decision engine for reading interests: request shape, answer parsing, engine switch.
No network: the HTTP call is replaced with canned answers."""

from __future__ import annotations

import os
import re
import unittest
from unittest import mock

from campusyamu.agents.preference import (GeminiDecisionInterpreter, LLMInterpreter, PreferenceInterpreter,
                                          engine_available, load_course_tags, preference_engine)
from campusyamu.agents.preference import decision

TAGS = load_course_tags()
COURSES = ["008", "013", "023", "024", "069"]       # Engineering, Physical Science, Architecture, Design, Dance


def interpreter() -> GeminiDecisionInterpreter:
    return GeminiDecisionInterpreter(TAGS, api_key="test-key")


def score(level: float) -> dict:
    return {"type": "score", "score": level, "confidence": 0.8}


class RequestTests(unittest.TestCase):
    def test_phrases_use_the_keyword_splitter(self) -> None:
        phrases, notes = GeminiDecisionInterpreter.phrases("Engineering, design and anything; engineering")
        self.assertEqual(phrases, ["Engineering", "design"])
        self.assertEqual(notes, ["'anything': no specific preference"])

    def test_questions_per_phrase_and_course(self) -> None:
        [payload] = interpreter().request_payloads("engineering, design", COURSES)
        q = payload["questions"]
        self.assertEqual(payload["model"], "gemini-decision-1")
        self.assertIn("engineering, design", payload["input"])
        self.assertIn("Match mark", payload["input"])                      # the scale lives in the shared input
        self.assertEqual(len(q), 2 * (3 + 2 * len(COURSES)))
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", k) for k in q))
        self.assertEqual(q["p0_interest"]["type"], "noul")
        self.assertEqual(len(q["p0_category"]["criteria"]), 17)
        self.assertIn("none", q["p0_course"]["criteria"])
        self.assertLessEqual(len(q["p0_course"]["criteria"]), 255)
        mark, miss = q["p1_m_024"], q["p1_x_024"]
        self.assertEqual((mark["type"], len(mark["criteria"])), ("score", 10))
        self.assertTrue(mark["criteria"][-1].startswith("10"))              # lowest -> highest
        self.assertTrue(miss["criteria"][0].startswith("-10") and miss["criteria"][-1].startswith("-1"))
        self.assertIn('"design"', mark["instructions"])
        self.assertIn("Design", mark["instructions"])

    def test_large_requests_are_split_at_1000_questions(self) -> None:
        payloads = interpreter().request_payloads("a, b, c, d, e", sorted(TAGS))
        self.assertGreater(len(payloads), 1)
        self.assertTrue(all(len(p["questions"]) <= decision.MAX_QUESTIONS for p in payloads))
        self.assertEqual(sum(len(p["questions"]) for p in payloads), 5 * (3 + 2 * len(TAGS)))
        self.assertTrue(all(p["input"] == payloads[0]["input"] for p in payloads))

    def test_no_text_no_request(self) -> None:
        self.assertEqual(interpreter().request_payloads("anything", COURSES), [])


class ParseTests(unittest.TestCase):
    ANSWERS = {
        "p0_interest": {"type": "noul", "noul": 0.97},
        "p0_category": {"type": "choice", "choice": "engineering",
                        "probabilities": {"engineering": 0.7, "built_environment": 0.28, "design": 0.02}},
        "p0_course": {"type": "choice", "choice": "none", "probabilities": {"none": 0.9, "008": 0.1}},
        "p0_m_008": score(9), "p0_x_008": score(9),          # Engineering: 10, -1
        "p0_m_013": score(1.2), "p0_x_013": score(6.6),      # Physical Science: 2, -3
        "p0_m_024": score(2), "p0_x_024": score(3),          # Design: 3, -7
        "p0_m_069": score(0), "p0_x_069": score(0),          # Dance: 1, -10
        "p1_interest": {"type": "noul", "noul": 0.9},
        "p1_category": {"type": "choice", "choice": "built_environment",
                        "probabilities": {"built_environment": 0.6, "engineering": 0.3}},
        "p1_course": {"type": "choice", "choice": "011", "probabilities": {"011": 0.85, "none": 0.15}},
        "p2_interest": {"type": "noul", "noul": 0.1},
        "p0_m_999": score(9),                                # unknown course: ignored
    }

    def test_marks_mismatches_categories_and_named_courses(self) -> None:
        result = interpreter().parse("engineering, quantity surveying, ummm", self.ANSWERS, COURSES)
        self.assertEqual(result.method, "llm")
        self.assertEqual(result.model, "gemini-decision-1")
        eng, qs = result.preferences
        self.assertEqual(eng.categories, ["engineering", "built_environment"])   # 2nd kept: 0.28 >= 0.25
        self.assertEqual(eng.courses, [])
        self.assertEqual({c: (eng.marks[c], eng.mismatches[c]) for c in ("008", "013", "024", "069")},
                         {"008": (10, -1), "013": (2, -3), "024": (3, -7), "069": (1, -10)})
        self.assertNotIn("999", eng.marks)
        self.assertIn("023", eng.marks)                                       # missing -> reviewed baseline
        self.assertTrue(any("missing from the LLM answer" in n for n in result.notes))
        self.assertEqual(qs.courses, ["011"])                                  # named with p >= 0.6
        self.assertEqual(qs.categories, ["built_environment", "engineering"])
        self.assertEqual(result.unmatched, ["ummm"])                           # not a study interest

    def test_weak_second_category_and_unsure_course_are_dropped(self) -> None:
        answers = {"p0_interest": {"noul": 0.9},
                   "p0_category": {"choice": "design", "probabilities": {"design": 0.8, "business": 0.2}},
                   "p0_course": {"choice": "024", "probabilities": {"024": 0.5, "none": 0.5}}}
        [pref] = interpreter().parse("creative", answers, COURSES).preferences
        self.assertEqual(pref.categories, ["design"])
        self.assertEqual(pref.courses, [])

    def test_interpret_merges_all_requests(self) -> None:
        gemini = interpreter()
        sent = []

        def fake_call(payload):
            sent.append(payload)
            return {"answers": {k: ({"noul": 0.9} if k.endswith("_interest") else
                                    {"choice": "engineering", "probabilities": {"engineering": 1.0}}
                                    if k.endswith("_category") else
                                    {"choice": "none", "probabilities": {"none": 1.0}}
                                    if k.endswith("_course") else score(4))
                                for k in payload["questions"]}}

        gemini._call = fake_call
        result = gemini.interpret("a, b, c, d, e", sorted(TAGS))
        self.assertGreater(len(sent), 1)
        self.assertEqual(len(result.preferences), 5)
        self.assertTrue(all(p.marks[c] == 5 and p.mismatches[c] == -6 for p in result.preferences for c in TAGS))
        self.assertFalse(any("missing" in n for n in result.notes))


class EngineSwitchTests(unittest.TestCase):
    def test_engine_comes_from_settings_then_env(self) -> None:
        from campusyamu.agents.preference import interpreter as module

        empty = lambda key, default=None: default                       # no settings.yaml value
        with mock.patch.dict(os.environ, {"PREFERENCE_ENGINE": ""}), mock.patch.object(module.settings, "get", empty):
            self.assertEqual(preference_engine(), "openai")             # built-in default
        yaml = lambda key, default=None: "gemini_decision" if key == "preferences.engine" else default
        with mock.patch.object(module.settings, "get", yaml):
            with mock.patch.dict(os.environ, {"PREFERENCE_ENGINE": ""}):
                self.assertEqual(preference_engine(), "gemini_decision")
            with mock.patch.dict(os.environ, {"PREFERENCE_ENGINE": "OpenAI"}):
                self.assertEqual(preference_engine(), "openai")         # .env wins, any case

    def test_env_picks_the_engine(self) -> None:
        env = {"PREFERENCE_ENGINE": "gemini_decision", "GEMINI_API_KEY": "k", "OPENAI_API_KEY": "o"}
        with mock.patch.dict(os.environ, env):
            self.assertIsInstance(PreferenceInterpreter(TAGS).llm, GeminiDecisionInterpreter)
            self.assertIsInstance(PreferenceInterpreter(TAGS, engine="openai").llm, LLMInterpreter)
            self.assertTrue(engine_available())

    def test_openai_model_does_not_leak_into_gemini(self) -> None:
        env = {"GEMINI_API_KEY": "k", "OPENAI_MODEL": "gpt-4o-mini", "PREFERENCE_DECISION_MODEL": ""}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(GeminiDecisionInterpreter(TAGS).model, "gemini-decision-1")

    def test_missing_key_or_unknown_engine_falls_back_to_keywords(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            p = PreferenceInterpreter(TAGS, engine="gemini_decision")
            self.assertIsNone(p.llm)
            self.assertFalse(engine_available("gemini_decision"))
            result = p.interpret("engineering", COURSES)
        self.assertEqual(result.method, "keywords")
        self.assertIn("GEMINI_API_KEY is not set", result.notes[-1])
        self.assertIn("unknown preference engine", PreferenceInterpreter(TAGS, engine="magic").reason)

    def test_failed_call_falls_back_to_keywords(self) -> None:
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}):
            p = PreferenceInterpreter(TAGS, engine="gemini_decision")
        p.llm._call = mock.Mock(side_effect=RuntimeError("Gemini Decisions HTTP 400: bad"))
        result = p.interpret("engineering", COURSES)
        self.assertEqual(result.method, "keywords")
        self.assertIn("HTTP 400", result.notes[-1])


if __name__ == "__main__":
    unittest.main()
