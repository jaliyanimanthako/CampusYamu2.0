from __future__ import annotations

import unittest

from RAG_Agent.graph_pipeline.al_clause_parsers import canonical_subject
from RAG_Agent.graph_pipeline.al_rule_semantics import (
    NotEvaluable,
    Student,
    compile_rule,
    equivalent_rule_sets,
    evaluate_rules,
)


def rule(**fields):
    base = {
        "target_id": "course:001",
        "requirement_type": "al_subject_combination",
        "eligible_streams": [],
        "subjects": [],
        "subject_groups": [],
        "minimum_grades": {
            "required_a_grades": 0,
            "required_b_grades": 0,
            "required_c_grades": 0,
            "required_s_grades": 3,
        },
        "subject_grade_requirements": [],
        "common_general_paper": {"required": False, "minimum_percentage": 0},
        "selection_constraints": [],
        "exception_to": "",
        "alternative_group": "",
        "alternative_option": 0,
    }
    return {**base, **fields}


def group(subjects, low=1, high=1):
    return {"subjects": subjects, "minimum_required": low, "maximum_allowed": high}


def student(*pairs, stream=None, cgp=30):
    return Student(tuple(pairs), stream, cgp)


SLOTS = [
    group(["Combined Mathematics", "Higher Mathematics"]),
    group(["Chemistry", "Physics"]),
    group(["Agricultural Science", "Combined Mathematics", "Biology", "Chemistry", "Physics"]),
]


class RuleSemanticsTests(unittest.TestCase):
    def test_slots_accept_overlapping_third_subject(self) -> None:
        rules = [rule(subject_groups=SLOTS)]
        ok = student(("Combined Mathematics", "S"), ("Chemistry", "S"), ("Physics", "S"))
        self.assertTrue(evaluate_rules(rules, ok))
        no_maths = student(("Biology", "S"), ("Chemistry", "S"), ("Physics", "S"))
        self.assertFalse(evaluate_rules(rules, no_maths))

    def test_pool_listing_in_subjects_is_informational(self) -> None:
        pool = ["Combined Mathematics", "Higher Mathematics", "Chemistry", "Physics",
                "Agricultural Science", "Biology"]
        self.assertTrue(
            equivalent_rule_sets([rule(subject_groups=SLOTS)],
                                 [rule(subject_groups=SLOTS, subjects=pool)])
        )

    def test_subject_named_only_in_subjects_is_required(self) -> None:
        third = [group(["Agricultural Science", "Physics", "Combined Mathematics"])]
        listed = rule(subjects=["Biology", "Chemistry"], subject_groups=third)
        explicit = rule(
            subject_groups=third,
            subject_grade_requirements=[
                {"subject": "Biology", "minimum_grade": "S", "alternatives": []},
                {"subject": "Chemistry", "minimum_grade": "S", "alternatives": []},
            ],
        )
        self.assertTrue(equivalent_rule_sets([listed], [explicit]))
        self.assertFalse(
            evaluate_rules(
                [listed],
                student(("Agricultural Science", "S"), ("Biology", "S"), ("Accounting", "S")),
            )
        )

    def test_one_of_written_three_ways_agrees(self) -> None:
        as_item = rule(subject_grade_requirements=[
            {"subject": "", "minimum_grade": "C",
             "alternatives": ["Combined Mathematics", "Physics"]}])
        as_alternatives = [
            rule(subject_grade_requirements=[
                {"subject": name, "minimum_grade": "C", "alternatives": []}],
                alternative_group="g", alternative_option=index)
            for index, name in enumerate(["Combined Mathematics", "Physics"], start=1)
        ]
        self.assertTrue(equivalent_rule_sets([as_item], as_alternatives))

    def test_invented_stream_is_a_real_disagreement(self) -> None:
        self.assertFalse(
            equivalent_rule_sets([rule(subject_groups=SLOTS)],
                                 [rule(subject_groups=SLOTS, eligible_streams=["Physical Science"])])
        )

    def test_university_minimum_makes_pass_counts_redundant(self) -> None:
        fewer = rule(minimum_grades={"required_s_grades": 2})
        self.assertTrue(equivalent_rule_sets([rule()], [fewer]))
        stricter = rule(minimum_grades={"required_c_grades": 1, "required_s_grades": 2})
        self.assertFalse(equivalent_rule_sets([rule()], [stricter]))

    def test_split_and_slash_names_are_repaired(self) -> None:
        compiled = compile_rule(rule(subject_groups=[group(
            ["Accounting", "Information & Communication", "Technology",
             "Mathematics/ Combined Mathematics"], 1, 0)]))
        self.assertEqual(
            set(compiled.groups[0][0]),
            {"Accounting", "Information & Communication Technology", "Mathematics",
             "Combined Mathematics"},
        )

    def test_unexecutable_rules_are_not_compared(self) -> None:
        garbled = rule(subject_groups=[group(["Christian Civilization Technology"])])
        self.assertIsNone(equivalent_rule_sets([garbled], [rule()]))
        pool = rule(selection_constraints=[{
            "constraint_type": "allowed_combination", "group_name": "", "count": 0,
            "subjects": ["Accounting", "Economics", "Physics", "Chemistry"]}])
        with self.assertRaises(NotEvaluable):
            compile_rule(pool)
        height = rule(requirement_type="other_admission_requirement")
        self.assertIsNone(equivalent_rule_sets([height], [height]))

    def test_only_from_limits_every_subject_to_the_lists(self) -> None:
        maths = ["Combined Mathematics", "Higher Mathematics"]
        others = ["Accounting", "Economics", "Physics"]
        rules = [rule(
            subject_groups=[group(maths, 1, 0)],
            selection_constraints=[{
                "constraint_type": "only_from", "group_name": "", "count": 0,
                "subjects": maths + others}],
        )]
        ok = student(("Combined Mathematics", "S"), ("Accounting", "S"), ("Physics", "S"))
        self.assertTrue(evaluate_rules(rules, ok))
        outside = student(("Combined Mathematics", "S"), ("Accounting", "S"), ("Biology", "S"))
        self.assertFalse(evaluate_rules(rules, outside))

    def test_unexecutable_reference_is_compared_both_ways(self) -> None:
        arts = {"constraint_type": "allowed_combination", "count": 3, "subjects": [],
                "group_name": "Arts Stream subjects selected per Section 2.2.1.1"}
        one_of = [group(["Economics", "Geography"], 1, 0)]
        split = [
            rule(minimum_grades={"required_s_grades": 3}, subject_groups=[], subjects=[]),
            rule(eligible_streams=["Arts"], subject_groups=one_of,
                 selection_constraints=[arts], minimum_grades={}),
        ]
        merged = [rule(eligible_streams=["Arts"], subject_groups=one_of,
                       selection_constraints=[arts])]
        self.assertTrue(equivalent_rule_sets(split, merged))
        missing_reference = [rule(eligible_streams=["Arts"], subject_groups=one_of)]
        self.assertFalse(equivalent_rule_sets(merged, missing_reference))
        # The Section 2.2.1.1 reference is decided by the Arts rules ...
        self.assertTrue(evaluate_rules(merged, student(
            ("Economics", "S"), ("Sinhala", "S"), ("Pali", "S"), stream="Arts")))
        self.assertFalse(evaluate_rules(merged, student(
            ("Economics", "S"), ("Buddhism", "S"), ("Buddhist Civilization", "S"), stream="Arts")))
        # ... while an unknown reference is still refused, never guessed.
        unknown = [rule(selection_constraints=[{**arts, "group_name": "Some other section"}])]
        with self.assertRaises(NotEvaluable):
            evaluate_rules(unknown, student(("Economics", "S"), ("Sinhala", "S"), ("Pali", "S")))

    def test_official_subject_names_resolve(self) -> None:
        self.assertEqual(canonical_subject("Islam Civilization"), "Islamic Civilization")
        self.assertEqual(canonical_subject("Western Music"), "Music")
        self.assertEqual(canonical_subject("History of Sri Lanka & India"), "History")
        self.assertEqual(canonical_subject("Malay"), "Malay")
        self.assertIsNone(canonical_subject("General English"))
        self.assertIsNone(canonical_subject("Common General Test"))


if __name__ == "__main__":
    unittest.main()
