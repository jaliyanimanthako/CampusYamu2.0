from __future__ import annotations

import unittest

from course_finder.finder import CourseFinder
from student_pipeline.graph import BAND_ORDER, build_pipeline, match_reports, run_pipeline

STUDENT = dict(stream="Physical Science", al=["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
               cgt=40, admission_district="Gampaha", home="Minuwangoda",
               ol=["Science:B", "English:B", "Maths:A"], z_score=1.56)


def _report(institution: str, year: str = "2024_2025", years: int = 5) -> dict:
    return {"institution": institution, "historical_summary": {"latest_academic_year": year},
            "comparison": {"years_compared": years}}


class StudentPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = CourseFinder()
        cls.app = build_pipeline(cls.finder)
        cls.state = run_pipeline(STUDENT, cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.finder.close()

    def rows(self, state=None):
        report = (state or self.state)["report"]
        return [row for band in BAND_ORDER for row in report["bands"][band]]

    def test_graph_shape(self) -> None:
        nodes = set(self.app.get_graph().nodes)
        self.assertTrue({"validate_profile", "find_courses", "analyze_course", "assemble"} <= nodes)

    def test_every_eligible_offering_gets_a_band(self) -> None:
        rows = self.rows()
        self.assertEqual(len(rows), len(self.state["candidates"]))
        self.assertEqual(len({r["uni_code"] for r in rows}), len(rows))          # no duplicates from branches
        self.assertEqual(sum(r["band"] == "no_history" for r in rows), 0)      # every option has cut-offs

    def test_uses_admission_district_cutoffs(self) -> None:
        engineering = next(r for r in self.rows() if r["uni_code"] == "008C")
        self.assertIn(engineering["band"], {"unlikely", "reach"})
        self.assertLess(engineering["expected_margin"], 0)
        colombo = run_pipeline({**STUDENT, "admission_district": "Colombo"}, self.app)
        other = next(r for r in self.rows(colombo) if r["uni_code"] == "008C")
        self.assertNotEqual(other["predicted_cutoff"], engineering["predicted_cutoff"])
        self.assertIn("Colombo district cut-offs", " ".join(colombo["report"]["notes"]))

    def test_without_z_score_no_analysis_runs(self) -> None:
        state = run_pipeline({**STUDENT, "z_score": None}, self.app)
        self.assertEqual(state["zscore_results"], [])
        self.assertTrue(all(r["band"] == "no_history" for r in self.rows(state)))

    def test_invalid_input_stops_early(self) -> None:
        state = run_pipeline({**STUDENT, "home": "Atlantis"}, self.app)
        self.assertIn("Atlantis", state["errors"][0])
        self.assertNotIn("report", state)

    def test_institution_name_variants(self) -> None:
        reports = [_report("Eastern University - Trincomalee Campus", "2022_2023"),
                   _report("Trincomalee Campus, Eastern University, Sri Lanka", "2024_2025"),
                   _report("University of Ruhuna")]
        match, how = match_reports("Trincomalee Campus", reports)
        # the KG's 'Trincomalee Campus' is canonicalised to the name the agent reports
        self.assertEqual((match["institution"], how), ("Trincomalee Campus, Eastern University, Sri Lanka",
                                                       "exact"))
        match, how = match_reports("Swamy Vipulananda Institute of Aesthetic Studies",
                                   [_report("Swami Vipulananda Institute of Aesthetic Studies")])
        self.assertEqual(how, "name_variant")
        self.assertEqual(match_reports("University of Colombo", reports), (None, "none"))


if __name__ == "__main__":
    unittest.main()
