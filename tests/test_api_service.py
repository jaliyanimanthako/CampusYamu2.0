from __future__ import annotations

import unittest

from campusyamu.api.service import AdvisorService, home_from_form

FORM = {"stream": "Physical Science",
        "al": [{"subject": "Combined Mathematics", "grade": "A"}, {"subject": "Physics", "grade": "B"},
               {"subject": "Chemistry", "grade": "C"}],
        "cgt": "40", "z_score": "1.56", "admission_district": "Kandy", "home_district": "Kandy",
        "home_town": "Katugastota",
        "ol": [{"subject": "Science", "grade": "B"}, {"subject": "English", "grade": "B"},
               {"subject": "Mathematics", "grade": ""}],
        "preferences": "engineering, design", "use_llm": False, "suggestions": "8"}


class AdvisorServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.web = AdvisorService()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web.finder.close()

    def test_options_for_the_dropdowns(self) -> None:
        o = self.web.options
        self.assertEqual(len(o["districts"]), 25)
        self.assertEqual(sum(len(v) for v in o["towns"].values()), 489)
        self.assertIn("Katugastota", o["towns"]["Kandy"])
        self.assertIn("Hettipola", o["towns"]["Matale"])
        self.assertIn("Hettipola", o["towns"]["Kurunegala"])                  # same name, two districts
        self.assertNotIn("Galle", o["towns"]["Kandy"])
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
        self.assertEqual((report["origin"]["town"], report["origin"]["district"]), ("Katugastota", "Kandy"))
        self.assertEqual(len(report["rankings"]["distance"]["suggestions"]), 8)
        self.assertNotIn("Mathematics", report["profile"]["ol_results"])          # "not given" is left out

    def test_validation_errors(self) -> None:
        status, data = self.web.run({**FORM, "home_town": "", "al": FORM["al"][:2]})
        self.assertEqual(status, 400)
        self.assertIn("home town", data["errors"][0])
        self.assertIn("three A/L subjects", data["errors"][0])
        status, data = self.web.run({**FORM, "al": [FORM["al"][0]] * 3})
        self.assertEqual((status, data["errors"]), (400, ["Choose three different A/L subjects"]))
        status, data = self.web.run({**FORM, "cgt": "abc"})
        self.assertEqual(status, 400)


class HomeFromFormTests(unittest.TestCase):
    def test_town_with_district(self) -> None:
        self.assertEqual(home_from_form({"home_town": "Hettipola", "home_district": "Matale"}), "Hettipola (Matale)")

    def test_forms_saved_before_home_towns(self) -> None:
        self.assertEqual(home_from_form({"ds_division": "Gangawata Korale"}), "Gangawata Korale")
        self.assertEqual(home_from_form({"home_town": "Kotugoda", "ds_division": "Minuwangoda"}), "Kotugoda")
        self.assertEqual(home_from_form({"home_district": "Kandy"}), "")


if __name__ == "__main__":
    unittest.main()
