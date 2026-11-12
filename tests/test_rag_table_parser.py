from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from campusyamu.knowledge_graph.parse_tables import (
    build_graph_data,
    write_graph_data,
)
from campusyamu.knowledge_graph.source_registry import PROJECT_ROOT, build_registry


class GraphTableParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = build_registry(PROJECT_ROOT)
        cls.data = build_graph_data(PROJECT_ROOT, cls.registry)

    def test_expected_entity_counts(self) -> None:
        counts = self.data["validation_summary"]["counts"]
        self.assertEqual(
            counts,
            {
                "academic_years": 1,
                "institutions": 20,
                "courses": 126,
                "course_offerings": 261,
                "uni_codes": 261,
                "subjects": 5,
                "ol_requirements": 85,
                "aptitude_tests": 24,
                "intake_records": 388,
            },
        )

    def test_intake_totals_reconcile(self) -> None:
        self.assertEqual(
            self.data["validation_summary"]["intake_totals"],
            {
                "course_total": 43_237,
                "offering_total": 42_337,
                "additional_total": 900,
            },
        )

    def test_every_offering_has_unicode_and_intake(self) -> None:
        offering_ids = {record["id"] for record in self.data["course_offerings"]}
        unicode_offerings = {
            record["offering_id"] for record in self.data["uni_codes"]
        }
        intake_offerings = {
            record["offering_id"]
            for record in self.data["intake_records"]
            if record["scope"] == "offering"
        }
        self.assertEqual(unicode_offerings, offering_ids)
        self.assertEqual(intake_offerings, offering_ids)

    def test_institution_hierarchy_is_explicit(self) -> None:
        institutions = {record["id"]: record for record in self.data["institutions"]}
        self.assertEqual(
            institutions["institution:sripalee-campus"]["parent_id"],
            "institution:university-of-colombo",
        )
        self.assertEqual(
            institutions["institution:trincomalee-campus"]["parent_id"],
            "institution:eastern-university-sri-lanka",
        )
        children = [item for item in institutions.values() if item["parent_id"]]
        self.assertEqual(len(children), 4)

    def test_distinct_ict_courses_are_not_merged(self) -> None:
        courses = {record["code"]: record for record in self.data["courses"]}
        self.assertEqual(
            courses["038"]["name"],
            "Information and Communication Technology (ICT)",
        )
        self.assertEqual(
            courses["104"]["name"],
            "Information Communication Technology",
        )

    def test_output_is_deterministic_and_valid_json(self) -> None:
        again = build_graph_data(PROJECT_ROOT, self.registry)
        self.assertEqual(self.data, again)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "graph_data.json"
            write_graph_data(self.data, output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                self.data,
            )


if __name__ == "__main__":
    unittest.main()
