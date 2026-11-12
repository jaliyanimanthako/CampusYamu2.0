"""Handbook "a 'C' in X or Y ... and 'S' grades in two OTHER subjects listed below"."""

from __future__ import annotations

import unittest

from campusyamu.knowledge_graph.al_rule_semantics import Student, evaluate_rules, uses_other_subjects
from campusyamu.knowledge_graph.build_graph import load_graph
from campusyamu.knowledge_graph.eligibility import EligibilityChecker, make_student

LIST = ["Combined Mathematics", "Higher Mathematics", "Mathematics", "Physics", "Chemistry",
        "Information & Communication Technology"]
C_RULE = {"target_id": "t", "subject_grade_requirements": [
    {"subject": "Combined Mathematics", "minimum_grade": "C", "alternatives": ["Physics", "Higher Mathematics"]}]}
OTHER_RULE = {"target_id": "t", "selection_constraints": [
    {"constraint_type": "minimum_count", "subjects": LIST, "count": 2,
     "condition": "At least 'S' grades in two other subjects listed below"}]}
PLAIN_RULE = {"target_id": "t", "selection_constraints": [
    {"constraint_type": "minimum_count", "subjects": LIST, "count": 2,
     "condition": "At least 'S' grades in two subjects listed below"}]}


def student(*pairs):
    return Student(tuple(pairs), "Physical Science", 40)


class SemanticsTests(unittest.TestCase):
    def test_other_subjects_cannot_reuse_the_grade_subject(self) -> None:
        bio = student(("Biology", "A"), ("Physics", "B"), ("Chemistry", "C"))
        maths = student(("Combined Mathematics", "A"), ("Physics", "B"), ("Chemistry", "C"))
        self.assertFalse(evaluate_rules([C_RULE, OTHER_RULE], bio))       # Physics can't count twice
        self.assertTrue(evaluate_rules([C_RULE, OTHER_RULE], maths))
        self.assertTrue(evaluate_rules([C_RULE, PLAIN_RULE], bio))        # without "other" the old reading holds
        # the grade subject may be any qualifying alternative: C in Physics, others CM + Chemistry
        self.assertTrue(evaluate_rules([C_RULE, OTHER_RULE],
                                       student(("Combined Mathematics", "S"), ("Physics", "C"), ("Chemistry", "S"))))

    def test_other_inside_one_rule(self) -> None:
        rule = {"target_id": "t",
                "subject_grade_requirements": [{"subject": "Combined Mathematics", "minimum_grade": "S"}],
                "selection_constraints": [{"constraint_type": "minimum_count", "subjects": ["Combined Mathematics", "Physics"],
                                           "count": 1, "condition": "and any other subject from the list"}]}
        self.assertFalse(evaluate_rules([rule], student(("Combined Mathematics", "A"), ("Biology", "S"), ("Art", "S"))))
        self.assertTrue(evaluate_rules([rule], student(("Combined Mathematics", "A"), ("Physics", "S"), ("Art", "S"))))

    def test_detection(self) -> None:
        self.assertTrue(uses_other_subjects(OTHER_RULE["selection_constraints"][0]))
        self.assertFalse(uses_other_subjects(PLAIN_RULE["selection_constraints"][0]))
        self.assertFalse(uses_other_subjects({"constraint_type": "maximum_count", "condition": "other"}))


class HandbookCoursesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_graph()
        cls.checker = EligibilityChecker(cls.graph)
        cls.ids = {a["name"]: n for n, a in cls.graph.nodes(data=True) if a["type"] == "Course"}

    def decide(self, course: str, subjects: list[str], stream: str = "Biological Science"):
        return self.checker.check_course(self.ids[course], make_student(subjects, stream, 40))

    def test_ai_and_computer_science(self) -> None:
        for course in ("Artificial Intelligence", "Computer Science"):
            bio = self.decide(course, ["Biology:A", "Physics:B", "Chemistry:C"])
            self.assertEqual(bio.decision, "not_eligible", course)
            self.assertIn("cannot count for both", bio.failed[0].reasons[0])
            self.assertEqual(self.decide(course, ["Biology:A", "Combined Mathematics:B", "Chemistry:C"]).decision,
                             "not_eligible")
            for ok in (["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
                       ["Physics:C", "Chemistry:S", "Information & Communication Technology:S"]):
                self.assertEqual(self.decide(course, ok, "Physical Science").decision, "eligible", (course, ok))


if __name__ == "__main__":
    unittest.main()
