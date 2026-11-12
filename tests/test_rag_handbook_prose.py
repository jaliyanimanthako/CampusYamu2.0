from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from RAG_Agent.graph_pipeline.handbook_prose import (
    HandbookProseError,
    extraction_schema,
    parse_handbook_structure,
    propose_rules,
    select_extraction_requests,
    validate_proposal,
)
from RAG_Agent.graph_pipeline.name_normalization import load_name_mappings
from RAG_Agent.graph_pipeline.normalize_names import normalize_graph_data
from RAG_Agent.graph_pipeline.parse_tables import build_graph_data
from RAG_Agent.graph_pipeline.source_registry import PROJECT_ROOT, build_registry, file_sha256


def force_llm_path():
    """Exercise the LLM harness on a unit that is now parsed deterministically."""

    return patch(
        "RAG_Agent.graph_pipeline.handbook_prose.deterministic_proposal",
        return_value=None,
    )


class HandbookProseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = build_registry(PROJECT_ROOT)
        table_data = build_graph_data(PROJECT_ROOT, registry)
        graph_data, _ = normalize_graph_data(table_data, load_name_mappings())
        cls.source_path = Path("RAG_Agent/student_handbook_english_structured.md")
        absolute_source = PROJECT_ROOT / cls.source_path
        cls.structure, cls.requests = parse_handbook_structure(
            absolute_source.read_text(encoding="utf-8"),
            graph_data,
            source_path=cls.source_path.as_posix(),
            source_checksum=file_sha256(absolute_source),
        )

    def test_deterministic_structure_covers_all_pages_and_courses(self) -> None:
        summary = self.structure["validation_summary"]
        self.assertEqual(summary["pdf_page_markers"], 208)
        self.assertEqual(summary["streams"], 8)
        self.assertEqual(summary["covered_courses"], 126)
        self.assertEqual(self.requests["request_count"], summary["extraction_units"])

    def test_large_arts_section_is_split_into_internal_course_blocks(self) -> None:
        requests = [
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
        ]
        self.assertEqual(len(requests), 17)
        general = next(
            item for item in requests if item["unit_key"] == "general-core"
        )
        basket_keys = {
            "basket-1",
            "basket-2",
            "basket-3",
            "basket-4",
            "cross-basket-exceptions",
        }
        communication = next(
            item for item in requests if item["unit_key"] == "special-3"
        )
        self.assertEqual(general["candidate_target_ids"], ["course:019"])
        self.assertTrue(
            basket_keys.issubset({item["unit_key"] for item in requests})
        )
        self.assertEqual(communication["candidate_target_ids"], ["course:029"])
        self.assertIn("Selection criteria", communication["evidence_text"])

    def test_shared_commerce_guidance_includes_preceding_courses(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.2.4"
        )
        self.assertEqual(request["target_scope"], "shared_with_preceding_sections")
        self.assertEqual(
            request["candidate_target_ids"],
            ["course:016", "course:017", "course:018", "course:028"],
        )

    def test_exact_request_id_selects_one_special_arts_block(self) -> None:
        request_id = "al-extraction:2.2.1.1:special-1"
        selected = select_extraction_requests(
            self.requests["requests"], request_ids=[request_id]
        )
        self.assertEqual([item["id"] for item in selected], [request_id])

    def test_unknown_request_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(HandbookProseError, "Unknown extraction request"):
            select_extraction_requests(
                self.requests["requests"], request_ids=["al-extraction:missing"]
            )

    def test_each_request_has_a_deterministic_clause_ledger(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"] == "general-core"
        )
        self.assertEqual(len(request["eligibility_clauses"]), 2)
        self.assertTrue(
            all(
                clause["scope_hint"] == "advanced_level_candidate"
                and clause["status"] == "pending"
                for clause in request["eligibility_clauses"]
            )
        )

    def test_no_rules_is_rejected_when_al_eligibility_was_detected(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"] == "special-2"
        )
        proposal = {
            "section_id": request["section_id"],
            "extraction_status": "no_rules",
            "rules": [],
            "clause_accounting": [
                {
                    "clause_id": request["eligibility_clauses"][0]["id"],
                    "disposition": "intentionally_ignored",
                    "rule_numbers": [],
                    "reason": "descriptive_not_eligibility",
                }
            ],
            "unresolved_text": [],
        }
        with self.assertRaisesRegex(HandbookProseError, "cannot be intentionally ignored"):
            validate_proposal(request, proposal)

    def test_structured_arts_units_are_parsed_without_model_calls(self) -> None:
        requests = [
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"]
            in {
                "general-core",
                "basket-1",
                "basket-2",
                "basket-3",
                "basket-4",
                "cross-basket-exceptions",
            }
        ]

        class NoCallModel:
            model = "must-not-be-called"

            def extract(self, request, schema, *, correction_history=()):
                raise AssertionError("Structured Arts parsing called the model")

        proposals, report = propose_rules(requests, NoCallModel())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["validated_rules"], 15)
        self.assertTrue(
            all(
                result["extraction_method"] == "deterministic"
                and result["semantic_status"] == "complete"
                for result in proposals["results"]
            )
        )

    def _request(self, request_id: str) -> dict:
        return next(
            item for item in self.requests["requests"] if item["id"] == request_id
        )

    def test_singular_pass_aptitude_clauses_are_detected_and_excluded(self) -> None:
        for request_id, fragment in (
            ("al-extraction:2.2.1.1:special-1", "To have a pass in the Aptitude Test"),
            ("al-extraction:2.2.8.7", "Pass the Aptitude Test"),
        ):
            clauses = self._request(request_id)["eligibility_clauses"]
            matches = [item for item in clauses if fragment in item["text"]]
            self.assertEqual(len(matches), 1, request_id)
            self.assertEqual(matches[0]["scope_hint"], "excluded_aptitude_test")

    def test_basket_one_all_three_subjects_rule_is_detected(self) -> None:
        clauses = self._request("al-extraction:2.2.1.1:basket-1")[
            "eligibility_clauses"
        ]
        self.assertIn(
            "all three subjects only from basket 01",
            clauses[1]["text"],
        )

    def test_cross_level_alternative_is_not_labelled_pure_ordinary_level(self) -> None:
        clauses = self._request("al-extraction:2.2.8.6")["eligibility_clauses"]
        cross = [
            item
            for item in clauses
            if item["scope_hint"] == "excluded_cross_level_alternative"
        ]
        self.assertEqual(len(cross), 1)
        self.assertIn("Advanced Level", cross[0]["text"])
        self.assertIn("Ordinary Level", cross[0]["text"])

    def test_subject_combination_block_is_parsed_without_model_calls(self) -> None:
        request = self._request("al-extraction:2.2.1.1:special-1")

        class NoCallModel:
            model = "must-not-be-called"

            def extract(self, request, schema, *, correction_history=()):
                raise AssertionError("Structured subject block called the model")

        proposals, report = propose_rules([request], NoCallModel())
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["model_calls"], 0)
        result = proposals["results"][0]
        self.assertEqual(result["extraction_method"], "deterministic")
        self.assertEqual(result["semantic_status"], "complete")
        rules = result["rules"]
        self.assertEqual(len(rules), 10)
        self.assertEqual(
            {rule["target_id"] for rule in rules}, {"course:020", "course:041"}
        )
        constraints = [
            (c["constraint_type"], c["group_name"], c["count"], tuple(c["subjects"]))
            for c in (rule["selection_constraints"][0] for rule in rules[:5])
        ]
        self.assertEqual(
            constraints,
            [
                ("minimum_count", "Arts Stream subjects", 3, ()),
                ("maximum_count", "Languages", 2, ()),
                ("maximum_count", "Religions and Civilizations basket", 1, ()),
                ("maximum_count", "Technological subject", 1, ()),
                (
                    "maximum_count",
                    "Listed subjects",
                    1,
                    ("Accounting", "Business Statistics", "Economics"),
                ),
            ],
        )
        reasons = {
            item["reason"]
            for item in result["clause_accounting"]
            if item["disposition"] == "intentionally_ignored"
        }
        self.assertEqual(
            reasons, {"ordinary_level_requirement", "aptitude_test_requirement"}
        )

    def test_subject_combination_parser_is_all_or_nothing(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import (
            deterministic_subject_combination_proposal,
        )

        request = dict(self._request("al-extraction:2.2.1.1:special-1"))
        clauses = [dict(item) for item in request["eligibility_clauses"]]
        clauses[2]["text"] = "2. Religions should be balanced with languages"
        request["eligibility_clauses"] = clauses
        self.assertIsNone(deterministic_subject_combination_proposal(request))

    def test_al_clause_cannot_use_an_ol_ignore_reason(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"] == "basket-2"
        )
        proposal = {
            "section_id": request["section_id"],
            "extraction_status": "needs_review",
            "rules": [],
            "clause_accounting": [
                {
                    "clause_id": clause["id"],
                    "disposition": "intentionally_ignored",
                    "rule_numbers": [],
                    "reason": "ordinary_level_requirement",
                }
                for clause in request["eligibility_clauses"]
            ],
            "unresolved_text": [
                clause["text"] for clause in request["eligibility_clauses"]
            ],
        }
        with self.assertRaisesRegex(HandbookProseError, "cannot be intentionally ignored"):
            validate_proposal(request, proposal)

    def test_medicine_section_is_bounded_and_resolved(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.3.1"
        )
        self.assertEqual(request["candidate_target_ids"], ["course:001"])
        self.assertEqual(request["source"]["pdf_page_start"], 58)
        self.assertIn("At least two ‘C’ grades", request["evidence_text"])

    def test_technology_section_without_four_part_number_is_included(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.7"
        )
        self.assertEqual(request["candidate_target_ids"], ["course:104"])

    def test_schema_is_strict_and_target_bounded(self) -> None:
        schema = extraction_schema(
            ["course:001"],
            section_id="course-section:2.2.3.1",
            section_number="2.2.3.1",
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["section_id"]["enum"],
            ["course-section:2.2.3.1"],
        )
        rule = schema["properties"]["rules"]["items"]
        self.assertFalse(rule["additionalProperties"])
        self.assertEqual(rule["properties"]["target_id"]["enum"], ["course:001"])
        self.assertEqual(
            rule["properties"]["source"]["properties"]["section"]["enum"],
            ["2.2.3.1"],
        )
        self.assertIn("eligible_streams", rule["required"])
        self.assertIn("common_general_paper", rule["required"])
        self.assertIn("selection_constraints", rule["required"])
        self.assertIn("clause_accounting", schema["required"])

    def test_grounded_proposal_is_accepted_but_remains_proposed(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.3.1"
        )
        clause_lines = [
            int(clause["markdown_line_start"])
            for clause in request["eligibility_clauses"]
        ]
        line_lookup = {
            int(item["markdown_line"]): item for item in request["evidence_lines"]
        }
        start, end = min(clause_lines), max(clause_lines)
        quote = "\n".join(
            str(line_lookup[number]["text"])
            for number in range(start, end + 1)
        )
        page = line_lookup[end]["pdf_page"]
        proposal = {
            "section_id": request["section_id"],
            "extraction_status": "rules_found",
            "rules": [
                {
                    "target_type": "Course",
                    "target_id": "course:001",
                    "requirement_type": "al_minimum_grades",
                    "eligible_streams": [],
                    "subjects": ["Biology", "Chemistry", "Physics"],
                    "subject_groups": [],
                    "minimum_grades": {
                        "required_a_grades": 0,
                        "required_b_grades": 0,
                        "required_c_grades": 2,
                        "required_s_grades": 1,
                        "grade_condition_text": (
                            "Two C grades and one S grade across the named subjects."
                        ),
                    },
                    "subject_grade_requirements": [],
                    "common_general_paper": {
                        "required": False,
                        "minimum_percentage": 0,
                        "condition": "",
                    },
                    "selection_constraints": [],
                    "exception_to": "",
                    "conditions": [],
                    "evidence_text": quote,
                    "source": {
                        "section": "2.2.3.1",
                        "pdf_page": page,
                        "markdown_line_start": start,
                        "markdown_line_end": end,
                    },
                    "confidence": "high",
                    "review_status": "proposed",
                }
            ],
            "clause_accounting": [
                {
                    "clause_id": clause["id"],
                    "disposition": "extracted",
                    "rule_numbers": [1],
                    "reason": "not_ignored",
                }
                for clause in request["eligibility_clauses"]
            ],
            "unresolved_text": [],
        }
        validated = validate_proposal(request, proposal)
        self.assertEqual(validated[0]["validation_status"], "passed")
        self.assertEqual(validated[0]["review_status"], "proposed")

        # Meaning checks: the excerpt never states a stream or names Accounting,
        # and names must be real A/L subjects.
        def with_rule(**changes):
            rule = {**proposal["rules"][0], **changes}
            return {**proposal, "rules": [rule]}

        with self.assertRaisesRegex(HandbookProseError, "Biological Science stream"):
            validate_proposal(request, with_rule(eligible_streams=["Biological Science"]))
        with self.assertRaisesRegex(HandbookProseError, "does not mention: Accounting"):
            validate_proposal(request, with_rule(subjects=["Biology", "Accounting"]))
        with self.assertRaisesRegex(HandbookProseError, "not an A/L subject"):
            validate_proposal(
                request, with_rule(subjects=["Biology", "Christian Civilization Technology"])
            )
        repaired = validate_proposal(
            request, with_rule(subjects=["biology", "Chemistry", "Physics"])
        )
        self.assertEqual(repaired[0]["subjects"], ["Biology", "Chemistry", "Physics"])

    def test_ungrounded_evidence_is_rejected(self) -> None:
        request = self.requests["requests"][0]
        proposal = {
            "section_id": request["section_id"],
            "extraction_status": "rules_found",
            "rules": [
                {
                    "target_type": "Course",
                    "target_id": request["candidate_target_ids"][0],
                    "requirement_type": "al_minimum_grades",
                    "evidence_text": "This sentence is not in the handbook.",
                    "source": {
                        "section": request["section_number"],
                        "pdf_page": request["source"]["pdf_page_start"],
                        "markdown_line_start": request["source"][
                            "markdown_line_start"
                        ],
                        "markdown_line_end": request["source"]["markdown_line_start"],
                    },
                    "review_status": "proposed",
                }
            ],
            "unresolved_text": [],
        }
        with self.assertRaises(HandbookProseError):
            validate_proposal(request, proposal)

    def test_proposal_progress_reports_start_and_completion(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.3.1"
        )
        clause_lines = [
            int(clause["markdown_line_start"])
            for clause in request["eligibility_clauses"]
        ]
        line_lookup = {
            int(item["markdown_line"]): item for item in request["evidence_lines"]
        }
        start, end = min(clause_lines), max(clause_lines)
        quote = "\n".join(
            str(line_lookup[number]["text"])
            for number in range(start, end + 1)
        )
        page = line_lookup[end]["pdf_page"]

        class FakeModel:
            model = "fake-model"

            def extract(self, request, schema, *, correction_history=()):
                return {
                    "section_id": request["section_id"],
                    "extraction_status": "rules_found",
                    "rules": [
                        {
                            "target_type": "Course",
                            "target_id": "course:001",
                            "requirement_type": "al_minimum_grades",
                            "eligible_streams": ["Biological Science"],
                            "subjects": ["Biology", "Chemistry", "Physics"],
                            "subject_groups": [],
                            "minimum_grades": {
                                "required_a_grades": 0,
                                "required_b_grades": 0,
                                "required_c_grades": 2,
                                "required_s_grades": 1,
                                "grade_condition_text": "Two C grades and one S grade.",
                            },
                            "subject_grade_requirements": [],
                            "common_general_paper": {
                                "required": False,
                                "minimum_percentage": 0,
                                "condition": "",
                            },
                            "selection_constraints": [],
                            "exception_to": "",
                            "conditions": [],
                            "evidence_text": quote,
                            "source": {
                                "section": request["section_number"],
                                "pdf_page": page,
                                "markdown_line_start": start,
                                "markdown_line_end": end,
                            },
                            "confidence": "high",
                            "review_status": "proposed",
                        }
                    ],
                    "clause_accounting": [
                        {
                            "clause_id": clause["id"],
                            "disposition": "extracted",
                            "rule_numbers": [1],
                            "reason": "not_ignored",
                        }
                        for clause in request["eligibility_clauses"]
                    ],
                    "unresolved_text": [],
                }

        events = []
        proposals, report = propose_rules(
            [request], FakeModel(), on_progress=events.append
        )
        self.assertEqual([event["event"] for event in events], [
            "section_started",
            "section_completed",
        ])
        self.assertEqual(report["validated_rules"], 1)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(proposals["results"]), 1)

    def test_focused_retry_can_resolve_an_isolated_clause(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"] == "special-4"
        )
        clause = request["eligibility_clauses"][0]

        class RetryModel:
            model = "fake-retry-model"

            def __init__(self):
                self.calls = 0

            def extract(self, model_request, schema, *, correction_history=()):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "section_id": model_request["section_id"],
                        "extraction_status": "needs_review",
                        "rules": [],
                        "clause_accounting": [
                            {
                                "clause_id": clause["id"],
                                "disposition": "needs_review",
                                "rule_numbers": [],
                                "reason": "not_ignored",
                            }
                        ],
                        "unresolved_text": [clause["text"]],
                    }
                return {
                    "section_id": model_request["section_id"],
                    "extraction_status": "rules_found",
                    "rules": [
                        {
                            "target_type": "Course",
                            "target_id": "course:031",
                            "requirement_type": "al_minimum_grades",
                            "eligible_streams": [],
                            "subjects": [],
                            "subject_groups": [],
                            "minimum_grades": {
                                "required_a_grades": 0,
                                "required_b_grades": 0,
                                "required_c_grades": 0,
                                "required_s_grades": 3,
                                "grade_condition_text": "Three S grades.",
                            },
                            "subject_grade_requirements": [],
                            "common_general_paper": {
                                "required": True,
                                "minimum_percentage": 30,
                                "condition": "30% or more",
                            },
                            "selection_constraints": [],
                            "exception_to": "",
                            "conditions": [],
                            "evidence_text": clause["text"],
                            "source": {
                                "section": model_request["section_number"],
                                "pdf_page": clause["pdf_page"],
                                "markdown_line_start": clause[
                                    "markdown_line_start"
                                ],
                                "markdown_line_end": clause["markdown_line_end"],
                            },
                            "confidence": "high",
                            "review_status": "proposed",
                        }
                    ],
                    "clause_accounting": [
                        {
                            "clause_id": clause["id"],
                            "disposition": "extracted",
                            "rule_numbers": [1],
                            "reason": "not_ignored",
                        }
                    ],
                    "unresolved_text": [],
                }

        model = RetryModel()
        with force_llm_path():
            proposals, report = propose_rules(
                [request], model, retry_needs_review=True
            )
        self.assertEqual(model.calls, 2)
        self.assertEqual(report["model_calls"], 2)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(proposals["results"][0]["retry_status"], "resolved")

    def test_validation_harness_replays_error_context_and_corrects(self) -> None:
        request = next(
            item
            for item in self.requests["requests"]
            if item["section_number"] == "2.2.1.1"
            and item["unit_key"] == "special-4"
        )
        clause = request["eligibility_clauses"][0]

        class CorrectingModel:
            model = "fake-correcting-model"

            def __init__(self):
                self.histories = []

            def extract(self, model_request, schema, *, correction_history=()):
                self.histories.append(list(correction_history))
                if not correction_history:
                    return {
                        "section_id": model_request["section_id"],
                        "extraction_status": "needs_review",
                        "rules": [],
                        "clause_accounting": [
                            {
                                "clause_id": clause["id"],
                                "disposition": "needs_review",
                                "rule_numbers": [],
                                "reason": "not_ignored",
                            }
                        ],
                        "unresolved_text": [],
                    }
                return {
                    "section_id": model_request["section_id"],
                    "extraction_status": "rules_found",
                    "rules": [
                        {
                            "target_type": "Course",
                            "target_id": "course:031",
                            "requirement_type": "al_minimum_grades",
                            "eligible_streams": [],
                            "subjects": [],
                            "subject_groups": [],
                            "minimum_grades": {
                                "required_a_grades": 0,
                                "required_b_grades": 0,
                                "required_c_grades": 0,
                                "required_s_grades": 3,
                                "grade_condition_text": "Three S grades.",
                            },
                            "subject_grade_requirements": [],
                            "common_general_paper": {
                                "required": True,
                                "minimum_percentage": 30,
                                "condition": "30% or more",
                            },
                            "selection_constraints": [],
                            "exception_to": "",
                            "conditions": [],
                            "evidence_text": clause["text"],
                            "source": {
                                "section": model_request["section_number"],
                                "pdf_page": clause["pdf_page"],
                                "markdown_line_start": clause[
                                    "markdown_line_start"
                                ],
                                "markdown_line_end": clause["markdown_line_end"],
                            },
                            "confidence": "high",
                            "review_status": "proposed",
                        }
                    ],
                    "clause_accounting": [
                        {
                            "clause_id": clause["id"],
                            "disposition": "extracted",
                            "rule_numbers": [1],
                            "reason": "not_ignored",
                        }
                    ],
                    "unresolved_text": [],
                }

        model = CorrectingModel()
        with force_llm_path():
            proposals, report = propose_rules([request], model, max_attempts=4)
        self.assertEqual(report["model_calls"], 2)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(model.histories[0]), 0)
        self.assertIn(
            "requires unresolved_text",
            model.histories[1][0]["validation_error"],
        )
        harness = proposals["results"][0]["harness"]
        self.assertEqual(harness["attempt_count"], 2)
        self.assertEqual(
            [item["status"] for item in harness["attempts"]],
            ["rejected", "accepted"],
        )

    # --- context-aware clause scoping -------------------------------------

    def test_ol_list_items_inherit_scope_from_their_intro_line(self) -> None:
        clauses = self._request("al-extraction:2.2.8.2")["eligibility_clauses"]
        scopes = {item["text"].strip(): item["scope_hint"] for item in clauses}
        self.assertEqual(
            scopes["- (a)   At least a Very Good Pass (B) in Mathematics"],
            "excluded_ordinary_level",
        )

    def test_owner_interpretation_selects_the_matching_model_answer(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import _apply_interpretation

        request, answer, _ = self._llm_unit_and_answer()
        strict, loose = answer(2, c_grades=1), answer(3)
        result = {
            "request_id": request["id"],
            "rules": validate_proposal(request, loose),
            "review_status": "unresolved",
            "review_basis": "model_disagreement",
            "verification": {"raw_proposal": strict},
        }
        all_s = {"subjects": ["Accounting", "Economics", "History"], "eligible": False}
        reading = {"reading": "one C needed", "cases": [all_s]}
        with force_llm_path():
            settled = _apply_interpretation(request, result, reading)
        self.assertEqual(settled["review_status"], "auto_accepted")
        self.assertEqual(settled["review_basis"], "owner_interpretation")
        self.assertEqual(settled["interpretation"]["selected"], "verifier")
        # Even when both models agree, an answer contradicting the owner loses.
        agreed = {**result, "review_status": "auto_accepted", "review_basis": "model_consensus"}
        overruled = _apply_interpretation(request, agreed, reading)
        self.assertEqual(overruled["review_status"], "unresolved")
        self.assertEqual(overruled["review_basis"], "contradicts_owner_interpretation")
        impossible = {"cases": [{**all_s, "eligible": None}, {**all_s, "eligible": True},
                                {**all_s, "eligible": False}]}
        unsettled = _apply_interpretation(request, result, impossible)
        self.assertEqual(unsettled["review_status"], "unresolved")
        self.assertFalse(unsettled["interpretation"]["applied"])

    def test_owner_stream_lists_reach_only_units_that_count_stream_subjects(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import _check_rule_meaning

        with_lists = {
            r["section_number"]: r["reference_stream_subjects"]
            for r in self.requests["requests"]
            if r["reference_stream_subjects"]
        }
        self.assertEqual(set(with_lists), {"2.2.8.2"})
        self.assertEqual(
            with_lists["2.2.8.2"]["Physical Science"],
            ["Combined Mathematics", "Physics", "Chemistry"],
        )
        rule = {"subjects": [], "selection_constraints": [{
            "constraint_type": "minimum_count", "group_name": "", "count": 2,
            "subjects": ["Biology", "Agricultural Science", "Combined Mathematics"]}]}
        text = "Two subjects from the Biological Science Stream or Physical Science Stream"
        _check_rule_meaning(dict(rule), text, with_lists["2.2.8.2"])
        with self.assertRaisesRegex(HandbookProseError, "does not mention"):
            _check_rule_meaning(dict(rule), text, None)

    def test_nursing_height_is_kept_as_other_admission_requirement(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        request = self._request("al-extraction:2.2.3.14")
        rules = validate_proposal(
            request, deterministic_proposal(request), ground_names=False
        )
        self.assertEqual(
            sorted(rule["requirement_type"] for rule in rules),
            ["al_subject_combination", "other_admission_requirement"],
        )
        height = next(r for r in rules if r["requirement_type"] == "other_admission_requirement")
        self.assertIn("in height", height["conditions"][0])

    def test_model_subject_group_without_subjects_is_rejected(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import _check_rule_meaning

        rule = {"subjects": [], "subject_groups": [
            {"name": "Stream subjects", "subjects": [], "minimum_required": 3,
             "maximum_allowed": 3, "condition": ""}]}
        with self.assertRaisesRegex(HandbookProseError, "use eligible_streams"):
            _check_rule_meaning(rule, "Three subjects in Biological Science Stream")

    def test_or_between_ol_and_al_list_items_is_cross_level(self) -> None:
        # "(i) O/L B grades ... / or / (ii) A/L S in English Language": the A/L
        # item is an alternative to an O/L requirement, not a mandatory A/L rule.
        clauses = self._request("al-extraction:2.2.8.24")["eligibility_clauses"]
        english = next(item for item in clauses if "English Language" in item["text"])
        ordinary = next(item for item in clauses if "Ordinary Level" in item["text"])
        self.assertEqual(english["scope_hint"], "excluded_cross_level_alternative")
        self.assertEqual(ordinary["scope_hint"], "excluded_cross_level_alternative")
        mandatory = [
            item for item in clauses if item["scope_hint"] == "advanced_level_candidate"
        ]
        self.assertEqual(len(mandatory), 1)
        self.assertIn("Sinhala or Tamil", mandatory[0]["text"])

    def test_future_academic_year_block_is_excluded(self) -> None:
        clauses = self._request("al-extraction:2.2.8.10")["eligibility_clauses"]
        future = [
            item
            for item in clauses
            if item["scope_hint"] == "excluded_other_academic_year"
        ]
        self.assertTrue(future)
        self.assertTrue(
            any("two ‘C’ grades and one ‘S’ grade" in item["text"] for item in future)
        )

    def test_programme_descriptions_and_practical_tests_are_excluded(self) -> None:
        def scopes(request_id):
            return {
                item["scope_hint"]
                for item in self._request(request_id)["eligibility_clauses"]
            }

        self.assertIn("excluded_descriptive", scopes("al-extraction:2.2.3.27"))
        self.assertIn("excluded_aptitude_test", scopes("al-extraction:2.2.8.19"))

    # --- deterministic clause parsers -------------------------------------

    def test_deterministic_coverage_floor_and_every_proposal_validates(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        converted = 0
        for request in self.requests["requests"]:
            proposal = deterministic_proposal(request)
            if proposal is None:
                continue
            validate_proposal(request, proposal, ground_names=False)  # raises on any defect
            converted += 1
        self.assertGreaterEqual(converted, 110)

    def test_or_separated_clauses_become_one_alternative_group(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        # 2.2.8.39: "...Engineering/Biosystem Technology Stream" OR "...any three of
        # the following list" -> two OR'd options, never two AND'd rules.
        request = self._request("al-extraction:2.2.8.39")
        rules = validate_proposal(request, deterministic_proposal(request))
        self.assertEqual(
            [(r["alternative_group"], r["alternative_option"]) for r in rules],
            [("alternatives-1", 1), ("alternatives-1", 2)],
        )

    def test_category_headings_become_alternatives(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        request = self._request("al-extraction:2.2.8.29")
        rules = validate_proposal(request, deterministic_proposal(request))
        self.assertEqual({r["alternative_option"] for r in rules}, {1, 2})
        self.assertEqual(rules[1]["eligible_streams"], ["Commerce"])
        # The "one of the following two categories" line is an intro, not a clause.
        self.assertFalse(
            any("two categories" in c["text"] for c in request["eligibility_clauses"])
        )

    def test_trailing_or_outside_the_ledger_still_declines(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        # 2.2.8.11 Category (B) continues with "or Two subjects including Accounting
        # ..." which is not a ledger clause; converting would drop that option.
        self.assertIsNone(deterministic_proposal(self._request("al-extraction:2.2.8.11")))

    def test_alternative_group_needs_two_options(self) -> None:
        request, answer, Fixed = self._llm_unit_and_answer()
        proposal = answer(3)
        proposal["rules"][0]["alternative_group"] = "alternatives-1"
        proposal["rules"][0]["alternative_option"] = 1
        with self.assertRaisesRegex(HandbookProseError, "at least two options"):
            validate_proposal(request, proposal)

    def test_consensus_ignores_alternative_group_labels(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import (
            _rule_signature,
            deterministic_proposal,
        )

        request = self._request("al-extraction:2.2.8.39")
        rules = validate_proposal(request, deterministic_proposal(request))
        relabelled = [
            {**rule, "alternative_group": "X", "alternative_option": 3 - rule["alternative_option"]}
            for rule in rules
        ]
        self.assertEqual(_rule_signature(rules), _rule_signature(relabelled))

    def test_requirement_text_outside_the_ledger_blocks_conversion(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        # 2.2.8.2 continues with "(i)/(ii)" stream options the ledger does not hold.
        self.assertIsNone(deterministic_proposal(self._request("al-extraction:2.2.8.2")))

    def test_combination_slots_are_expanded_and_deduplicated(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        proposal = deterministic_proposal(self._request("al-extraction:2.2.3.4"))
        combos = [
            frozenset(item["subjects"])
            for item in proposal["rules"][0]["selection_constraints"]
        ]
        self.assertEqual(len(combos), len(set(combos)))
        self.assertIn(
            frozenset({"Chemistry", "Mathematics", "Agricultural Science"}), combos
        )

    def test_medicine_grade_counts(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        rule = deterministic_proposal(self._request("al-extraction:2.2.3.1"))["rules"][0]
        self.assertEqual(rule["minimum_grades"]["required_c_grades"], 2)
        self.assertEqual(rule["minimum_grades"]["required_s_grades"], 1)
        self.assertEqual(
            sorted(rule["subjects"]), ["Biology", "Chemistry", "Physics"]
        )

    # --- automated review -------------------------------------------------

    def _llm_unit_and_answer(self):
        request = self._request("al-extraction:2.2.1.1:special-4")
        clause = request["eligibility_clauses"][0]
        rule = {
            "target_type": "Course",
            "target_id": "course:031",
            "requirement_type": "al_minimum_grades",
            "eligible_streams": [],
            "subjects": [],
            "subject_groups": [],
            "minimum_grades": {
                "required_a_grades": 0,
                "required_b_grades": 0,
                "required_c_grades": 0,
                "required_s_grades": 3,
                "grade_condition_text": "",
            },
            "subject_grade_requirements": [],
            "common_general_paper": {
                "required": True,
                "minimum_percentage": 30,
                "condition": "",
            },
            "selection_constraints": [],
            "exception_to": "",
            "conditions": [],
            "evidence_text": clause["text"],
            "source": {
                "section": request["section_number"],
                "pdf_page": clause["pdf_page"],
                "markdown_line_start": clause["markdown_line_start"],
                "markdown_line_end": clause["markdown_line_end"],
            },
            "confidence": "high",
            "review_status": "proposed",
        }

        def answer(s_grades, c_grades=0):
            return {
                "section_id": request["section_id"],
                "extraction_status": "rules_found",
                "rules": [
                    {
                        **rule,
                        "minimum_grades": {
                            **rule["minimum_grades"],
                            "required_s_grades": s_grades,
                            "required_c_grades": c_grades,
                        },
                    }
                ],
                "clause_accounting": [
                    {
                        "clause_id": clause["id"],
                        "disposition": "extracted",
                        "rule_numbers": [1],
                        "reason": "not_ignored",
                    }
                ],
                "unresolved_text": [],
            }

        class Fixed:
            def __init__(self, name, proposal):
                self.model = name
                self.proposal = proposal

            def extract(self, request, schema, *, correction_history=()):
                return self.proposal

        return request, answer, Fixed

    def test_verifier_agreement_is_auto_accepted(self) -> None:
        request, answer, Fixed = self._llm_unit_and_answer()
        with force_llm_path():
            proposals, report = propose_rules(
                [request], Fixed("primary", answer(3)), verifier=Fixed("verifier", answer(3))
            )
        result = proposals["results"][0]
        self.assertEqual(result["review_status"], "auto_accepted")
        self.assertEqual(result["review_basis"], "model_consensus")
        self.assertEqual(report["model_calls"], 2)
        self.assertEqual(report["review_counts"]["auto_accepted"], 1)

    def test_verifier_disagreement_is_unresolved_and_queued(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import build_review_queue

        request, answer, Fixed = self._llm_unit_and_answer()
        with force_llm_path():
            proposals, _ = propose_rules(
                [request],
                Fixed("primary", answer(3)),
                # One C and two S passes admits fewer students than three S passes.
                verifier=Fixed("verifier", answer(2, c_grades=1)),
            )
        result = proposals["results"][0]
        self.assertEqual(result["verification"]["comparison"], "semantic")
        self.assertEqual(result["review_status"], "unresolved")
        self.assertEqual(result["review_basis"], "model_disagreement")
        queue = build_review_queue(proposals)
        self.assertFalse(queue["blocking"])
        self.assertEqual(queue["item_count"], 1)

    def test_only_open_merge_keeps_accepted_and_replaces_open(self) -> None:
        from RAG_Agent.graph_pipeline import handbook_prose
        from RAG_Agent.graph_pipeline.handbook_prose import merge_proposals, open_requests

        request, answer, Fixed = self._llm_unit_and_answer()
        deterministic = self._request("al-extraction:2.2.3.2")
        real = handbook_prose.deterministic_proposal
        only_request_is_llm = patch(
            "RAG_Agent.graph_pipeline.handbook_prose.deterministic_proposal",
            side_effect=lambda item: None if item["id"] == request["id"] else real(item),
        )
        with only_request_is_llm:
            old, _ = propose_rules([request], Fixed("old", answer(3)))
            self.assertEqual(old["results"][0]["review_status"], "unverified")
            self.assertEqual(
                [item["id"] for item in open_requests([deterministic, request], old)],
                [request["id"]],
            )
            fresh, _ = propose_rules(
                [request], Fixed("new", answer(3)), verifier=Fixed("check", answer(3))
            )
            self.assertEqual(open_requests([request], fresh), [])
            merged, report, dropped = merge_proposals(
                old, fresh, [deterministic, request]
            )
        self.assertEqual(dropped, [])
        by_id = {result["request_id"]: result for result in merged["results"]}
        self.assertEqual(by_id[request["id"]]["review_status"], "auto_accepted")
        self.assertEqual(by_id[request["id"]]["model"], "new")
        self.assertEqual(by_id[request["id"]]["verifier_model"], "check")
        self.assertEqual(by_id[deterministic["id"]]["extraction_method"], "deterministic")
        self.assertEqual(report["review_counts"]["auto_accepted"], 2)

    def test_course_dependent_credit_subject_uses_stated_examples(self) -> None:
        from RAG_Agent.graph_pipeline.handbook_prose import deterministic_proposal

        request = self._request("al-extraction:2.2.1.1:special-8")
        rules = validate_proposal(request, deterministic_proposal(request))
        by_course = {
            request["candidate_target_names"][rule["target_id"]]: (
                rule["subject_grade_requirements"][0]["subject"],
                rule["confidence"],
            )
            for rule in rules
        }
        # Stated in the clause's own examples -> high confidence.
        self.assertEqual(by_course["Music"], ("Music", "high"))
        self.assertEqual(by_course["Visual Arts"], ("Art", "high"))
        # Not stated; same-named A/L subject -> medium and flagged in the text.
        self.assertEqual(by_course["Dance"], ("Dance", "medium"))
        dance = next(r for r in rules if r["target_id"] == "course:069")
        self.assertIn("does not state it", dance["conditions"][0])

    def test_header_only_units_return_no_rules_without_model_calls(self) -> None:
        requests = [
            self._request(f"al-extraction:2.2.2.{number}") for number in (1, 2, 3)
        ]

        class NoCallModel:
            model = "must-not-be-called"

            def extract(self, request, schema, *, correction_history=()):
                raise AssertionError("header-only unit called the model")

        proposals, report = propose_rules(requests, NoCallModel())
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(report["failures"], [])
        self.assertTrue(
            all(
                result["extraction_status"] == "no_rules"
                and result["review_status"] == "auto_accepted"
                for result in proposals["results"]
            )
        )
        # Their requirements come from the shared Commerce guidance unit.
        shared = self._request("al-extraction:2.2.2.4")
        self.assertTrue(
            {"course:016", "course:017", "course:028"}.issubset(
                shared["candidate_target_ids"]
            )
        )

    def test_deterministic_units_are_auto_accepted(self) -> None:
        request = self._request("al-extraction:2.2.3.2")

        class NoCallModel:
            model = "must-not-be-called"

            def extract(self, request, schema, *, correction_history=()):
                raise AssertionError("deterministic unit called the model")

        proposals, report = propose_rules([request], NoCallModel(), verifier=NoCallModel())
        self.assertEqual(proposals["results"][0]["review_status"], "auto_accepted")
        self.assertEqual(report["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
