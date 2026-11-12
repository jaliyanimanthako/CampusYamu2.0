from __future__ import annotations

import unittest

from course_finder.finder import CourseFinder
from ranking_agent import CUTOFF_WEIGHT, build_rankings, distance_order, preference_order, zscore_order
from student_pipeline.graph import build_pipeline, run_pipeline

STUDENT = dict(stream="Physical Science", al=["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
               cgt=40, admission_district="Gampaha", home="Minuwangoda",
               ol=["Science:B", "English:B", "Maths:A"], z_score=1.56)


def row(code, band, cutoff, pref=None, car=30):
    return {"uni_code": code, "course_name": code, "band": band, "latest_cutoff": cutoff,
            "latest_year": "2024_2025", "preference_score": pref, "car_min": car}


ROWS = [row("S1", "strong", 1.20, 9.0), row("S2", "strong", 1.50, 5.0), row("C1", "competitive", 1.55, 6.0),
        row("R1", "reach", 1.60, 2.0), row("U1", "unlikely", 1.90, 1.0), row("U2", "unlikely", 2.10, 8.0),
        row("N1", "no_history", None, 10.0)]


class OrderTests(unittest.TestCase):
    def test_zscore_order_bands_then_highest_cutoff(self) -> None:
        ranking = zscore_order(ROWS)
        self.assertEqual([s["uni_code"] for s in ranking["suggestions"]], ["U2", "U1", "R1", "C1", "S2", "S1"])
        self.assertEqual([s["position"] for s in ranking["suggestions"]], [1, 2, 3, 4, 5, 6])
        self.assertIn("1 option(s) without a numeric cut-off", ranking["notes"][0])

    def test_preference_order_mark_plus_weighted_cutoff(self) -> None:
        ranking = preference_order(ROWS)
        scores = {s["uni_code"]: s["combined_score"] for s in ranking["suggestions"]}
        self.assertEqual(CUTOFF_WEIGHT, 2.5)
        self.assertEqual(scores["U2"], round(8.0 + 2.5 * 2.10, 2))
        self.assertEqual(scores["S1"], round(9.0 + 2.5 * 1.20, 2))
        self.assertEqual(ranking["cutoff_weight"], 2.5)
        ordered = [s["combined_score"] for s in ranking["suggestions"]]
        self.assertEqual(ordered, sorted(ordered, reverse=True))
        self.assertEqual(ranking["suggestions"][0]["uni_code"], "U2")         # 13.25 beats S1's 12.0
        self.assertNotIn("N1", scores)                                         # no cut-off, not ranked

    def test_distance_order_punishes_far_sites(self) -> None:
        near = row("NEAR", "strong", 1.50, 8.0, car=30)
        far = row("FAR", "strong", 1.50, 8.0, car=540)
        farther_but_better = row("FB", "strong", 1.80, 8.0, car=300)
        no_travel = row("NT", "strong", 1.50, 8.0, car=None)
        ranking = distance_order([far, near, farther_but_better, no_travel], mode="fixed")
        by_code = {s["uni_code"]: s for s in ranking["suggestions"]}
        self.assertEqual(by_code["FAR"]["distance_penalty"], -2.0)               # 9 h costs 2 points
        self.assertEqual(by_code["NEAR"]["combined_score"], round(8.0 + 2.5 * 1.5 - 2 * 30 / 540, 2))
        self.assertEqual(by_code["FB"]["combined_score"], round(8.0 + 2.5 * 1.8 - 2 * 300 / 540, 2))
        self.assertEqual([s["uni_code"] for s in ranking["suggestions"]], ["NEAR", "FB", "FAR"])
        self.assertIn("travel time", ranking["notes"][0])
        # same rows without distance: order 2 ties NEAR and FAR, and FB wins
        self.assertEqual(preference_order([far, near, farther_but_better])["suggestions"][0]["uni_code"], "FB")

    def test_equal_mode_gives_distance_the_cutoff_spread(self) -> None:
        rows = [row("NEAR_LOW", "strong", 1.0, 8.0, car=20), row("FAR_HIGH", "strong", 2.0, 8.0, car=420),
                row("MID", "strong", 1.5, 8.0, car=220)]
        ranking = distance_order(rows)                                           # default mode: equal
        self.assertEqual(ranking["mode"], "equal")
        self.assertEqual(ranking["distance_points"], 2.5)                       # 2.5 x (2.0 - 1.0)
        by_code = {s["uni_code"]: s for s in ranking["suggestions"]}
        self.assertEqual(by_code["NEAR_LOW"]["distance_penalty"], 0.0)
        self.assertEqual(by_code["MID"]["distance_penalty"], -1.25)
        self.assertEqual(by_code["FAR_HIGH"]["distance_penalty"], -2.5)
        # the cut-off gain and the distance loss cancel exactly: all three tie on score
        self.assertEqual({s["combined_score"] for s in ranking["suggestions"]}, {10.5})
        self.assertEqual(ranking["suggestions"][0]["uni_code"], "NEAR_LOW")     # tie -> nearest first
        with self.assertRaises(ValueError):
            distance_order(rows, mode="nope")

    def test_limit_and_no_interests(self) -> None:
        many = [row(f"X{i}", "strong", 1 + i / 100, 5.0) for i in range(30)]
        self.assertEqual(len(zscore_order(many)["suggestions"]), 20)
        self.assertEqual(len(preference_order(many)["suggestions"]), 20)
        self.assertEqual(len(distance_order(many)["suggestions"]), 20)
        self.assertEqual(distance_order([row("A", "strong", 1.0)])["suggestions"], [])
        empty = preference_order([row("A", "strong", 1.0)])
        self.assertEqual(empty["suggestions"], [])
        self.assertIn("no interests", empty["notes"][0])


class PipelineRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = CourseFinder()
        cls.app = build_pipeline(cls.finder, use_llm=False)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.finder.close()

    def test_pipeline_report_has_both_orders(self) -> None:
        report = run_pipeline({**STUDENT, "preferences": "design, planning, computers"}, self.app)["report"]
        rankings = report["rankings"]
        self.assertEqual(list(rankings), ["zscore", "preference", "distance"])
        zs = rankings["zscore"]["suggestions"]
        self.assertEqual(len(zs), 20)
        self.assertEqual(zs[0]["band"], "unlikely")
        bands = [s["band"] for s in zs]
        self.assertEqual(bands, sorted(bands, key=["unlikely", "reach", "competitive", "strong"].index))
        pref = rankings["preference"]["suggestions"]
        self.assertEqual(len(pref), 20)
        dist = rankings["distance"]["suggestions"]
        self.assertEqual(len(dist), 20)
        d = rankings["distance"]
        span = d["farthest_car_min"] - d["nearest_car_min"]
        self.assertAlmostEqual(d["distance_points"], 2.5 * (d["cutoff_range"][1] - d["cutoff_range"][0]), delta=0.01)
        for s in dist:
            expected = (s["preference_score"] + 2.5 * s["latest_cutoff"]
                        - d["distance_points"] * (s["car_min"] - d["nearest_car_min"]) / span)
            self.assertAlmostEqual(s["combined_score"], expected, delta=0.011)
        plain = {**rankings, "distance": {k: v for k, v in rankings["distance"].items()
                                          if k not in ("analysis", "feedback")}}
        self.assertEqual(plain, build_rankings(report))                         # + analysis and feedback on order 3                     # node output = pure function
        self.assertIn("rank_suggestions", set(self.app.get_graph().nodes))


if __name__ == "__main__":
    unittest.main()
