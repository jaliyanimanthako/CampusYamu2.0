from __future__ import annotations

import unittest

from campusyamu.web.server import WebApp

FORM = {"stream": "Physical Science",
        "al": [{"subject": "Combined Mathematics", "grade": "A"}, {"subject": "Physics", "grade": "B"},
               {"subject": "Chemistry", "grade": "C"}],
        "cgt": "40", "z_score": "1.56", "admission_district": "Kandy", "home_district": "Kandy",
        "ds_division": "Gangawata Korale",
        "ol": [{"subject": "Science", "grade": "B"}, {"subject": "English", "grade": "B"},
               {"subject": "Mathematics", "grade": ""}],
        "preferences": "engineering, design", "use_llm": False, "suggestions": "8"}


class WebAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.web = WebApp()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web.finder.close()

    def test_options_for_the_dropdowns(self) -> None:
        o = self.web.options
        self.assertEqual(len(o["districts"]), 25)
        self.assertEqual(sum(len(v) for v in o["ds_divisions"].values()), 339)
        self.assertIn("Gangawata Korale", o["ds_divisions"]["Kandy"])
        self.assertNotIn("Karandeniya", o["ds_divisions"]["Kandy"])
        self.assertIn("Physical Science", o["streams"])
        self.assertIn("Combined Mathematics", o["al_subjects"])
        self.assertEqual(len(o["al_subjects"]), len(set(o["al_subjects"])))

    def test_stream_hints(self) -> None:
        hints = self.web.options["stream_hints"]
        self.assertEqual(set(hints), set(self.web.options["streams"]))
        bio = hints["Biological Science"]
        self.assertEqual(bio["source"], "owner stream_subjects")
        self.assertIn("Biology", bio["defaults"])
        self.assertNotIn("Combined Mathematics", bio["allowed"])
        for stream, hint in hints.items():
            self.assertTrue(set(hint["defaults"]) <= set(self.web.options["al_subjects"]), stream)

    def test_bio_subjects_do_not_get_ai(self) -> None:
        form = {**FORM, "stream": "Biological Science",
                "al": [{"subject": "Biology", "grade": "A"}, {"subject": "Physics", "grade": "B"},
                       {"subject": "Chemistry", "grade": "C"}]}
        status, data = self.web.run(form)
        self.assertEqual(status, 200)
        names = {r["course_name"] for band in data["report"]["bands"].values() for r in band}
        self.assertNotIn("Artificial Intelligence", names)
        self.assertNotIn("Computer Science", names)

    def test_run_offline(self) -> None:
        status, data = self.web.run({**FORM, "use_llm": True} if not self.web.options["llm_available"] else FORM)
        self.assertEqual(status, 200)
        report = data["report"]
        self.assertFalse(data["used_llm"])
        self.assertEqual(report["origin"]["ds_division"], "Gangawata Korale")
        self.assertEqual(len(report["rankings"]["distance"]["suggestions"]), 8)
        self.assertNotIn("Mathematics", report["profile"]["ol_results"])          # "not given" is left out

    def test_validation_errors(self) -> None:
        status, data = self.web.run({**FORM, "ds_division": "", "al": FORM["al"][:2]})
        self.assertEqual(status, 400)
        self.assertIn("home DS division", data["errors"][0])
        self.assertIn("three A/L subjects", data["errors"][0])
        status, data = self.web.run({**FORM, "al": [FORM["al"][0]] * 3})
        self.assertEqual((status, data["errors"]), (400, ["Choose three different A/L subjects"]))
        status, data = self.web.run({**FORM, "cgt": "abc"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
