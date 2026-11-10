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


if __name__ == "__main__":
    unittest.main()
