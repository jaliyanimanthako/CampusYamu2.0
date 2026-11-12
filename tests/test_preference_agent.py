from __future__ import annotations

import json
import unittest

from campusyamu.agents.course_finder.finder import CourseFinder
from campusyamu.agents.preference import (CATEGORY_BY_ID, Interpretation, KeywordInterpreter, LLMInterpreter, Preference,
                              PreferenceInterpreter, categorize, load_course_tags)
from campusyamu.agents.preference.interpreter import baseline_mark, baseline_mismatch
from campusyamu.knowledge_graph.build_graph import load_graph
from campusyamu.pipeline.graph import build_pipeline, run_pipeline

STUDENT = dict(stream="Physical Science", al=["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
               cgt=40, admission_district="Gampaha", home="Minuwangoda",
               ol=["Science:B", "English:B", "Maths:A"], z_score=1.56)


class CourseTagTests(unittest.TestCase):
    def test_every_kg_course_has_a_valid_primary_category(self) -> None:
        tags = load_course_tags()
        graph = load_graph()
        courses = {a["code"]: a["name"] for _, a in graph.nodes(data=True) if a["type"] == "Course"}
        self.assertEqual(set(tags), set(courses))
        for code, tag in tags.items():
            self.assertEqual(tag.name, courses[code])
            self.assertTrue(set(tag.marks) <= set(CATEGORY_BY_ID))
            self.assertTrue(all(1 <= m <= 10 for m in tag.marks.values()))
            self.assertGreaterEqual(tag.marks[tag.primary], 7, tag.name)       # every course is clearly about something
        architecture = tags["023"]
        self.assertEqual(architecture.primary, "built_environment")
        self.assertEqual((architecture.mark("design"), architecture.mark("law")), (8, 1))

    def test_baseline_marks(self) -> None:
        tags = load_course_tags()
        design = Preference(1, "design", ["design"])
        self.assertEqual(baseline_mark(tags["024"], design), 10)                 # Design
        self.assertEqual(baseline_mark(tags["023"], design), 8)                  # Architecture
        self.assertEqual(baseline_mark(tags["001"], design), 1)                  # Medicine
        two = Preference(1, "buildings", ["engineering", "built_environment"])
        self.assertEqual(baseline_mark(tags["023"], two), round(10 * 0.85))       # 2nd category discounted
        self.assertEqual(baseline_mark(tags["023"], Preference(1, "x", ["law"], ["023"])), 10)   # named

    def test_baseline_mismatch(self) -> None:
        tags = load_course_tags()
        by_name = {t.name: t for t in tags.values()}
        engineering = Preference(1, "engineering", ["engineering"])
        miss = {n: baseline_mismatch(by_name[n], engineering)
                for n in ("Engineering", "Physical Science", "Design", "Dance")}
        self.assertEqual(miss, {"Engineering": -1, "Physical Science": -3, "Design": -7, "Dance": -10})
        # low match either way, but Design is a much bigger miss than Physical Science
        self.assertEqual((baseline_mark(by_name["Design"], engineering),
                          baseline_mark(by_name["Physical Science"], engineering)), (3, 1))
        self.assertEqual(baseline_mismatch(by_name["Dance"], Preference(1, "x", ["law"], [by_name["Dance"].code])), -1)
        self.assertTrue(all(-10 <= baseline_mismatch(t, engineering) <= -1 for t in tags.values()))


class KeywordInterpreterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.interpreter = KeywordInterpreter(load_course_tags())

    def cats(self, text: str) -> list[list[str]]:
        return [p.categories for p in self.interpreter.interpret(text).preferences]

    def test_order_synonyms_and_typos(self) -> None:
        result = self.interpreter.interpret("Engineering, desing, town planning; maths")
        self.assertEqual([p.categories[0] for p in result.preferences],
                         ["engineering", "design", "built_environment", "mathematics"])
        self.assertEqual([p.rank for p in result.preferences], [1, 2, 3, 4])
        self.assertEqual(result.preferences[0].courses, [])                     # a category word, not a course
        self.assertEqual(self.cats("I like to study computer science"), [["computing"]])
        self.assertEqual(self.cats("medicine or law"), [["health"], ["law"]])

    def test_named_course_and_no_preference(self) -> None:
        result = self.interpreter.interpret("quantity surveying, anything, astrology")
        self.assertEqual(result.preferences[0].courses, ["011"])
        self.assertEqual(result.unmatched, ["astrology"])
        self.assertTrue(any("no specific preference" in n for n in result.notes))
        self.assertEqual(self.interpreter.interpret("").preferences, [])


class LLMInterpreterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tags = load_course_tags()
        self.llm = LLMInterpreter(self.tags, model="test-model", api_key="test")

    def test_payload_is_strict_and_lists_every_category(self) -> None:
        payload = self.llm.request_payload("design and buildings", ["023", "024", "023"])
        fmt = payload["text"]["format"]
        self.assertTrue(fmt["strict"])
        item = fmt["schema"]["properties"]["preferences"]["items"]
        self.assertEqual(set(item["properties"]["categories"]["items"]["enum"]), set(CATEGORY_BY_ID))
        self.assertEqual(len(item["properties"]["course_codes"]["items"]["enum"]), len(self.tags))
        mark = item["properties"]["marks"]["items"]["properties"]
        self.assertEqual(mark["course_code"]["enum"], ["023", "024"])           # only the courses to mark
        self.assertEqual(mark["mark"]["enum"], list(range(1, 11)))
        self.assertEqual(mark["mismatch"]["enum"], list(range(-10, 0)))
        self.assertIn("mismatch", item["properties"]["marks"]["items"]["required"])
        sent = json.loads(payload["input"][1]["content"])
        self.assertEqual(sent["courses_to_mark"][0]["category_marks"], self.tags["023"].marks)
        self.assertFalse(payload["store"])

    def test_answer_is_validated(self) -> None:
        raw = {"preferences": [{"phrase": "fashion", "categories": ["design", "made_up"], "course_codes": [],
                                "marks": [{"course_code": "034", "mark": 10, "mismatch": -1},
                                          {"course_code": "023", "mark": 14, "mismatch": 3},
                                          {"course_code": "999", "mark": 5, "mismatch": -2}]},
                               {"phrase": "architecture", "categories": [], "course_codes": ["023", "999"],
                                "marks": [{"course_code": "023", "mark": 6}]},
                               {"phrase": "stars", "categories": [], "course_codes": [], "marks": []}],
               "unmatched": ["hmm"]}
        result = self.llm.parse("fashion, architecture, stars", raw, ["023", "034", "001"])
        self.assertEqual([(p.rank, p.categories, p.courses) for p in result.preferences],
                         [(1, ["design"], []), (2, ["built_environment"], ["023"])])
        fashion, architecture = result.preferences
        self.assertEqual(fashion.marks, {"023": 10, "034": 10, "001": 1})        # 14 clamped; 001 from baseline
        self.assertEqual(fashion.mismatches["023"], -1)                          # +3 clamped into -10..-1
        self.assertEqual(fashion.mismatches["001"], -10)                         # Medicine vs design: baseline
        self.assertEqual(architecture.marks["023"], 10)                          # a named course is always 10
        self.assertEqual(result.unmatched, ["hmm", "stars"])
        self.assertTrue(any("missing from the LLM answer" in n for n in result.notes))

    def test_failure_falls_back_to_keywords(self) -> None:
        auto = PreferenceInterpreter(self.tags, use_llm=False)
        auto.llm = self.llm

        def boom(_payload):
            raise RuntimeError("offline")
        self.llm._call = boom
        result = auto.interpret("engineering")
        self.assertEqual((result.method, result.preferences[0].categories), ("keywords", ["engineering"]))
        self.assertIn("offline", result.notes[0])


class CategorizeTests(unittest.TestCase):
    def test_marks_order_groups_and_other(self) -> None:
        tags = load_course_tags()
        rows = [{"uni_code": c + "X", "course_code": c, "course_name": tags[c].name, "car_min": car}
                for c, car in (("023", 50), ("024", 70), ("030", 60), ("001", 5), ("100", 20))]
        interp = KeywordInterpreter(tags).interpret("design, planning", [r["course_code"] for r in rows])
        tagged, report = categorize(rows, interp, tags)
        design = [(r["uni_code"], r["mark"]) for r in report["groups"][0]["rows"]]
        self.assertEqual(design, [("024X", 10), ("023X", 8), ("100X", 6)])      # highest mark first
        planning = [r["uni_code"] for r in report["groups"][1]["rows"]]
        self.assertEqual(planning, ["023X", "030X"])                             # equal marks: nearest first
        by_code = {r["uni_code"]: r for r in tagged}
        architecture = by_code["023X"]
        self.assertEqual([(m["mark"], m["mismatch"], m["net"]) for m in architecture["preference_marks"]],
                         [(8, -3, 5), (10, -1, 9)])
        self.assertEqual(architecture["preference_score"], 8.1)                  # net 9 for interest 2 x 0.9
        self.assertEqual(architecture["preference_rank"], 2)
        self.assertIsNone(by_code["001X"]["preference_rank"])                    # Medicine: in "other"
        self.assertEqual(report["other"]["count"], 1)
        self.assertEqual(by_code["001X"]["preference_score"], -9)                # Medicine: 1 + (-10) for both
        self.assertEqual([r["uni_code"] for r in report["poor_fit"]["rows"]], ["001X"])
        self.assertEqual([r["uni_code"] for r in report["best_overall"]][:2], ["024X", "023X"])

    def test_later_interest_still_lists_the_course(self) -> None:
        tags = load_course_tags()
        rows = [{"uni_code": "023X", "course_code": "023", "course_name": "Architecture", "car_min": 1}]
        interp = Interpretation("a, b, c, d", "keywords", [
            Preference(1, "a", ["engineering"], marks={"023": 4}), Preference(2, "b", ["law"], marks={"023": 1}),
            Preference(3, "c", ["law"], marks={"023": 1}), Preference(4, "d", ["design"], marks={"023": 5})])
        tagged, report = categorize(rows, interp, tags)
        self.assertEqual(report["groups"][3]["count"], 1)
        self.assertEqual(tagged[0]["preference_rank"], 4)                        # listed, so not in "other"
        self.assertEqual(report["other"]["count"], 0)


class PipelinePreferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = CourseFinder()
        cls.app = build_pipeline(cls.finder, use_llm=False)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.finder.close()

    def test_groups_eligible_courses_by_preference(self) -> None:
        state = run_pipeline({**STUDENT, "preferences": "engineering, design, planning, medicine"}, self.app)
        prefs = state["report"]["preferences"]
        self.assertEqual(prefs["method"], "keywords")
        groups = {g["phrase"]: g for g in prefs["groups"]}
        self.assertIn("008F", {r["uni_code"] for r in groups["engineering"]["rows"]})
        planning = {r["course_name"] for r in groups["planning"]["rows"]}
        self.assertTrue({"Architecture", "Urban Informatics and Planning", "Quantity Surveying"} <= planning)
        marks = [r["mark"] for r in groups["design"]["rows"]]
        self.assertEqual(marks, sorted(marks, reverse=True))
        self.assertEqual(groups["design"]["rows"][0]["mark"], 10)
        medicine = {r["course_code"] for r in groups["medicine"]["rows"]}
        self.assertNotIn("001", medicine)                                       # MBBS is not open to this student
        self.assertIn("054", medicine)                                          # Physiotherapy is
        rows = [r for b in state["report"]["bands"].values() for r in b]
        self.assertTrue(all(r["categories"] for r in rows))
        self.assertTrue(all(len(r["preference_marks"]) == 4 for r in rows))     # a mark per interest, every row
        for r in rows:
            for m in r["preference_marks"]:
                self.assertEqual(m["net"], m["mark"] + m["mismatch"])
                self.assertTrue(-10 <= m["mismatch"] <= -1)
        self.assertEqual(prefs["other"]["count"], sum(r["preference_rank"] is None for r in rows))

    def test_without_preferences_nothing_changes(self) -> None:
        state = run_pipeline(STUDENT, self.app)
        self.assertEqual(state["report"]["preferences"]["method"], "none")
        self.assertEqual(state["report"]["preferences"]["groups"], [])
        self.assertIn("score_preferences", set(self.app.get_graph().nodes))


if __name__ == "__main__":
    unittest.main()
