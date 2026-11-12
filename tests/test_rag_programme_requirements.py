from __future__ import annotations

import json
import unittest
from pathlib import Path

from campusyamu.knowledge_graph.al_rule_semantics import Student, evaluate_rules
from campusyamu.knowledge_graph.handbook_prose import (
    OWNER_INTERPRETATIONS,
    deterministic_proposal,
    parse_handbook_structure,
)
from campusyamu.knowledge_graph.name_normalization import load_name_mappings
from campusyamu.knowledge_graph.normalize_names import normalize_graph_data
from campusyamu.knowledge_graph.parse_tables import build_graph_data
from campusyamu.knowledge_graph.programme_requirements import build_programme_requirements
from campusyamu.knowledge_graph.source_registry import PROJECT_ROOT, build_registry, file_sha256


def student(*subjects, stream="Commerce"):
    return Student(tuple((name, "S") for name in subjects), stream, 30)


class ProgrammeRequirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = build_registry(PROJECT_ROOT)
        graph, _ = normalize_graph_data(
            build_graph_data(PROJECT_ROOT, registry), load_name_mappings()
        )
        path = PROJECT_ROOT / "data/raw/handbook/student_handbook_english_structured.md"
        _, requests = parse_handbook_structure(
            path.read_text(encoding="utf-8"),
            graph,
            source_path="data/raw/handbook/student_handbook_english_structured.md",
            source_checksum=file_sha256(path),
        )
        cls.requests = requests["requests"]
        owner = json.loads(Path(OWNER_INTERPRETATIONS).read_text(encoding="utf-8"))
        cls.output = build_programme_requirements(
            cls.requests, graph, owner["programme_rules"]
        )
        cls.programmes = {p["id"]: p for p in cls.output["programmes"]}

    def _requirements_for(self, university, fragment):
        return [
            r for r in self.output["requirements"]
            if self.programmes[r["programme_id"]]["university"] == university
            and fragment in self.programmes[r["programme_id"]]["name"]
        ]

    def test_commerce_course_rule_no_longer_needs_a_model(self) -> None:
        request = next(r for r in self.requests if r["section_number"] == "2.2.2.4")
        scopes = [c["scope_hint"] for c in request["eligibility_clauses"]]
        self.assertEqual(scopes.count("excluded_programme_level"), 2)
        self.assertIsNotNone(deterministic_proposal(request))

    def test_accounting_finance_programmes_require_accounting(self) -> None:
        forensic = self._requirements_for("University of Kelaniya", "Auditing and Forensic")
        self.assertEqual(len(forensic), 1)
        self.assertEqual(forensic[0]["review_basis"], "owner_interpretation")
        rule = forensic[0]["rule"]
        self.assertFalse(evaluate_rules([rule], student("Business Studies", "Economics", "Geography")))
        self.assertTrue(evaluate_rules([rule], student("Business Studies", "Economics", "Accounting")))
        self.assertEqual(self._requirements_for("University of Kelaniya", "Marketing"), [])

    def test_owner_extensions_insurance_and_trincomalee(self) -> None:
        self.assertEqual(len(self._requirements_for("University of Kelaniya", "Honours in Insurance")), 1)
        trinco = self._requirements_for(
            "Trincomalee Campus of the Eastern University, Sri Lanka", "Accounting and Finance")
        self.assertEqual(len(trinco), 1)
        self.assertEqual(self._requirements_for(
            "Trincomalee Campus of the Eastern University, Sri Lanka", "Marketing"), [])

    def test_ruhuna_footnote_applies_to_marked_programme_only(self) -> None:
        finance = self._requirements_for("University of Ruhuna", "Finance")
        bases = sorted(r["review_basis"] for r in finance)
        self.assertEqual(bases, ["handbook_footnote", "owner_interpretation"])
        footnote = next(r for r in finance if r["review_basis"] == "handbook_footnote")
        self.assertTrue(evaluate_rules(
            [footnote["rule"]], student("Accounting", "Economics", "Business Statistics")))
        self.assertFalse(evaluate_rules(
            [footnote["rule"]], student("Accounting", "Economics", "Geography")))
        self.assertFalse(evaluate_rules(
            [footnote["rule"]], student("Accounting", "Economics", "Business Studies", stream="Arts")))
        marketing = self._requirements_for("University of Ruhuna", "Marketing")
        self.assertEqual(marketing, [])

    def test_every_programme_resolves_to_an_institution(self) -> None:
        self.assertTrue(all(p["institution_id"] for p in self.output["programmes"]))
        self.assertEqual(self.output["unmatched_footnotes"], [])


if __name__ == "__main__":
    unittest.main()
