from __future__ import annotations

import unittest

from campusyamu.knowledge_graph.arts_rules import check_arts_combination
from campusyamu.knowledge_graph.build_graph import UNIVERSITY_MINIMUM_ID, build_graph
from campusyamu.knowledge_graph.eligibility import EligibilityChecker, make_student
from campusyamu.knowledge_graph.source_registry import PROJECT_ROOT


class ArtsRuleTests(unittest.TestCase):
    def test_handbook_examples_and_basket_rules(self) -> None:
        cases = [
            (["Economics", "Geography", "History"], True),
            (["Sinhala", "Pali", "Sanskrit"], True),           # handbook example
            (["Sinhala", "Tamil", "English"], True),           # three National Languages
            (["Pali", "Sanskrit", "Arabic"], False),           # three Classical
            (["Chinese", "French", "Economics"], True),        # handbook example
            (["Chinese", "French", "Japanese"], False),        # three Foreign
            (["Chinese", "French", "Buddhism"], True),         # two languages + basket 02
            (["Buddhism", "Buddhist Civilization", "Economics"], False),
            (["Music", "Music", "Economics"], False),          # same basket 03 area
            (["Art", "Dance", "Buddhism"], False),             # no basket 01, no exception
            (["Civil Technology", "Food Technology", "Economics"], False),
            (["Physics", "Economics", "History"], False),      # not an Arts subject
        ]
        for subjects, expected in cases:
            with self.subTest(subjects=subjects):
                self.assertEqual(check_arts_combination(subjects).eligible, expected)


class KnowledgeGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph, cls.report = build_graph(PROJECT_ROOT)
        cls.checker = EligibilityChecker(cls.graph)

    def check(self, course, subjects, stream, cgp=50):
        return self.checker.check_course(course, make_student(subjects, stream, cgp))

    def test_architecture_owner_reading(self) -> None:
        """§2.2.8.6/§2.2.8.8: >=1 from list (i); all three from (i) allowed; the rest from list (ii)."""

        cases = [
            (["Combined Mathematics:A", "Physics:B", "Chemistry:C"], "Physical Science", "eligible"),
            (["Chemistry:S", "Physics:S", "Accounting:S"], None, "eligible"),
            (["Art:S", "Accounting:S", "Economics:S"], None, "eligible"),
            (["Accounting:S", "Economics:S", "History:S"], None, "not_eligible"),   # nothing from (i)
            (["Art:S", "Accounting:S", "Music:S"], None, "not_eligible"),          # Music in neither list
        ]
        for course in ("course:023", "course:097"):
            for subjects, stream, expected in cases:
                with self.subTest(course=course, subjects=subjects):
                    self.assertEqual(self.check(course, subjects, stream).decision, expected)

    def test_graph_validates_and_every_course_has_the_university_minimum(self) -> None:
        self.assertEqual(self.report["problems"], [])
        courses = [n for n, a in self.graph.nodes(data=True) if a["type"] == "Course"]
        self.assertEqual(len(courses), 126)
        for course in courses:
            self.assertIn(UNIVERSITY_MINIMUM_ID, self.graph[course])

    def test_medicine_grades_and_university_minimum(self) -> None:
        self.assertEqual(self.check("course:001", ["Biology:A", "Chemistry:A", "Physics:B"],
                                    "Biological Science").decision, "eligible")
        weak = self.check("course:001", ["Biology:A", "Chemistry:S", "Physics:S"], "Biological Science")
        self.assertEqual(weak.decision, "not_eligible")
        self.assertIn("two ‘C’ grades", weak.failed[0].evidence_text)
        low_cgp = self.check("course:001", ["Biology:A", "Chemistry:A", "Physics:A"],
                             "Biological Science", cgp=20)
        self.assertEqual(low_cgp.decision, "not_eligible")
        self.assertIn("§1.2", low_cgp.failed[0].citation)

    def test_arts_course_uses_basket_rules(self) -> None:
        self.assertEqual(self.check("course:019", ["Economics", "Sinhala", "Pali"], "Arts").decision,
                         "eligible")
        bad = self.check("course:019", ["Buddhism", "Buddhist Civilization", "Economics"], "Arts")
        self.assertEqual(bad.decision, "not_eligible")
        self.assertIn("Buddhism cannot be offered with Buddhist Civilization", bad.failed[0].reasons)

    def test_non_al_conditions_are_listed_not_checked(self) -> None:
        nursing = self.check("course:037", ["Biology", "Chemistry", "Physics"], "Biological Science")
        self.assertEqual(nursing.decision, "eligible")
        self.assertTrue(any("in height" in c for c in nursing.additional_conditions))

    def test_programme_requirements_follow_the_course(self) -> None:
        commerce = self.check("course:018", ["Business Studies", "Economics", "Geography"], "Commerce")
        self.assertEqual(commerce.decision, "eligible")
        finance = [p for p in commerce.programme_requirements if "Finance" in p["programme"]]
        self.assertTrue(finance and not any(p["met"] for p in finance))
        with_accounting = self.check("course:018", ["Business Studies", "Economics", "Accounting"],
                                     "Commerce")
        self.assertTrue(all(p["met"] for p in with_accounting.programme_requirements))

    def test_viewer_payload_covers_graph_with_readable_rules(self) -> None:
        from campusyamu.knowledge_graph.graph_viewer import build_payload

        payload = build_payload(self.graph)
        self.assertEqual(len(payload["nodes"]), self.graph.number_of_nodes())
        self.assertEqual(len(payload["edges"]), self.graph.number_of_edges())
        medicine = [
            n for n in payload["nodes"]
            if n["type"] == "Requirement" and "two ‘C’ grades" in n["details"].get("handbook text", "")
        ]
        self.assertTrue(medicine)
        self.assertIn("Grades: at least 2 × C, 1 × S", medicine[0]["details"]["rule"])

    def test_viewer_page_embeds_data_and_pinned_library(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from campusyamu.knowledge_graph.graph_viewer import FORCE_GRAPH_URL, write_viewer

        with tempfile.TemporaryDirectory() as tmp:
            html = write_viewer(self.graph, _Path(tmp) / "viewer.html").read_text(encoding="utf-8")
        self.assertIn(FORCE_GRAPH_URL, html)
        self.assertIn("force-graph@1.51.4", FORCE_GRAPH_URL)
        self.assertNotIn("__DATA__", html)
        self.assertIn('"group": "Biological Science"', html)

    def test_unknown_subject_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_student(["Biology", "Chemistry", "Astrology"], "Biological Science", 50)


if __name__ == "__main__":
    unittest.main()
