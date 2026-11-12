from __future__ import annotations

import unittest

from campusyamu.knowledge_graph.name_normalization import load_name_mappings
from campusyamu.knowledge_graph.normalize_names import normalize_graph_data
from campusyamu.knowledge_graph.parse_tables import build_graph_data
from campusyamu.knowledge_graph.source_registry import PROJECT_ROOT, build_registry


class GraphNameNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = build_registry(PROJECT_ROOT)
        graph_data = build_graph_data(PROJECT_ROOT, registry)
        cls.normalized, cls.report = normalize_graph_data(
            graph_data,
            load_name_mappings(),
        )

    def test_normalization_passes_without_collisions(self) -> None:
        self.assertEqual(self.report["status"], "passed")
        self.assertEqual(self.report["collisions"], [])
        self.assertEqual(self.report["unresolved_aliases"], [])
        self.assertEqual(self.report["stable_id_validation"], "passed")

    def test_course_aliases_resolve_to_canonical_ids(self) -> None:
        lookup = self.normalized["entity_resolution"]["courses"]
        self.assertEqual(lookup["performing arts"], "course:041")
        self.assertEqual(
            lookup["applied sciences bio sc"],
            "course:007",
        )
        self.assertEqual(
            lookup["polymer science and industrial mgt"],
            "course:139",
        )

    def test_institution_aliases_resolve_to_child_nodes(self) -> None:
        lookup = self.normalized["entity_resolution"]["institutions"]
        self.assertEqual(
            lookup["sripalee campus university of colombo"],
            "institution:sripalee-campus",
        )
        self.assertEqual(
            lookup["trincomalee campus eastern university sri lanka"],
            "institution:trincomalee-campus",
        )

    def test_protected_ict_courses_remain_distinct(self) -> None:
        protected = self.report["protected_course_distinctions"]
        self.assertEqual(len(protected), 1)
        self.assertEqual(protected[0]["status"], "distinct")
        self.assertEqual(
            protected[0]["course_ids"],
            ["course:038", "course:104"],
        )

    def test_offering_can_be_resolved_by_unicode_and_names(self) -> None:
        lookup = self.normalized["entity_resolution"]["course_offerings"]
        self.assertEqual(lookup["041s"], "offering:041:sripalee-campus")
        self.assertEqual(
            lookup["performing arts::sripalee campus"],
            "offering:041:sripalee-campus",
        )

    def test_normalization_is_deterministic(self) -> None:
        registry = build_registry(PROJECT_ROOT)
        graph_data = build_graph_data(PROJECT_ROOT, registry)
        again, report = normalize_graph_data(graph_data, load_name_mappings())
        self.assertEqual(self.normalized, again)
        self.assertEqual(self.report, report)


if __name__ == "__main__":
    unittest.main()
