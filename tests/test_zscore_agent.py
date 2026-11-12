"""One end-to-end output check for the public agent contract."""

import unittest
from pathlib import Path

from zscore_agent import ZScoreAgent


DATABASE = Path(__file__).parents[1] / "data" / "z_scores.db"


class ZScoreAgentOutputTest(unittest.TestCase):
    def test_medicine_gampaha_output(self) -> None:
        result = ZScoreAgent(DATABASE).analyze(
            district="Gampaha",
            course="Medicine",
            z_score=2.10,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["input"],
            {"district": "Gampaha", "course": "Medicine", "z_score": 2.10},
        )
        self.assertGreater(result["total_reports"], 0)
        self.assertGreater(result["calibration"]["backtest_count"], 100)
        self.assertGreaterEqual(result["calibration"]["observed_coverage"], 0.79)

        colombo_report = next(
            report
            for report in result["reports"]
            if report["institution"] == "University of Colombo"
        )
        self.assertEqual(colombo_report["district"], "Gampaha")
        self.assertEqual(
            colombo_report["historical_summary"]["latest_cutoff"],
            2.4035,
        )
        self.assertEqual(colombo_report["comparison"]["years_compared"], 6)
        self.assertEqual(colombo_report["historical_alignment"], "low")
        self.assertEqual(colombo_report["evidence_confidence"], "high")




class NameTolerantMatchingTest(unittest.TestCase):
    """The tables spell courses/institutions differently across years."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = ZScoreAgent(DATABASE)

    def institutions(self, **kwargs):
        result = self.agent.analyze(district="Gampaha", z_score=1.5, **kwargs)
        return {r["institution"]: r for r in result["reports"]}

    def test_abbreviated_course_names_match(self) -> None:
        # 'APPLIED SCIENCES (PHY.SC)' / 'APPLIED SCIENCES PHY.SC'
        reports = self.institutions(course="Applied Sciences (Physical Science)")
        self.assertIn("Wayamba University of Sri Lanka", reports)
        # 'University of Jaffna - Vavuniya Campus' years merge into University of Vavuniya
        self.assertEqual(reports["University of Vavuniya, Sri Lanka"]["comparison"]["years_compared"], 5)
        self.assertIn("University of Kelaniya", self.institutions(course="Peace and Conflict Resolution"))

    def test_stream_specific_cutoffs(self) -> None:
        any_subject = self.institutions(course="Management Studies (TV)", stream="Physical Science")
        commerce = self.institutions(course="Management Studies (TV)", stream="Commerce")
        trinco = "Trincomalee Campus, Eastern University, Sri Lanka"
        self.assertNotEqual(any_subject[trinco]["historical_summary"]["latest_cutoff"],
                            commerce[trinco]["historical_summary"]["latest_cutoff"])
        both = self.agent.analyze(district="Gampaha", course="Management Studies (TV)", z_score=1.5)
        self.assertEqual({r["course"] for r in both["reports"]},
                         {"Management Studies (TV) — A (commerce)", "Management Studies (TV) — B (any)"})


if __name__ == "__main__":
    unittest.main()
