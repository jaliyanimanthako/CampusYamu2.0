from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from campusyamu.agents.course_finder.cli import interactive_profile, main
from campusyamu.agents.course_finder.finder import (APTITUDE, BLOCKED_OL, CHECK_OL, OPEN, CourseFinder, ProfileError,
                                  StudentProfile)

STUDENT = dict(stream="Physical Science", al=["Combined Mathematics:A", "Physics:B", "Chemistry:C"],
               cgt=40, admission_district="Gampaha", home="Minuwangoda",
               ol=["Science:B", "English:B", "Maths:A"], z_score=1.56)


class CourseFinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = CourseFinder()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.finder.close()

    def find(self, **changes):
        return self.finder.find_courses(StudentProfile.from_inputs(**{**STUDENT, **changes}))

    def course(self, result, code):
        return next(c for c in result.courses if c.course_code == code)

    def test_reference_student(self) -> None:
        result = self.find()
        groups = result.by_group()
        self.assertEqual(len(groups["can_apply"]) + len(groups["with_conditions"]), 55)
        self.assertEqual(len(groups["not_eligible"]), 71)
        self.assertEqual(result.origin["ds_division"], "Minuwangoda")
        architecture = self.course(result, "023").offerings[0]
        self.assertEqual((architecture.uni_code, architecture.status), ("023G", APTITUDE))
        engineering = self.course(result, "008")
        self.assertEqual(engineering.offerings[0].uni_code, "008C")             # nearest first (Siddamulla)
        self.assertEqual(engineering.best_status, OPEN)
        self.assertIn("Z-score 1.56 recorded for the next step", " ".join(result.notes))

    def test_ol_failures_block_offerings(self) -> None:
        result = self.find(ol=["Science:B", "English:W", "Maths:S"])
        landscape = self.course(result, "097").offerings[0]
        self.assertEqual(landscape.status, BLOCKED_OL)                # English fails outright ...
        self.assertEqual(landscape.ol_failed, ["O/L English ≥ S (you have W)"])
        self.assertIn("confirm whether A/L Combined Mathematics counts", landscape.ol_unknown[0])  # ... Maths open
        business = self.course(result, "109").offerings[0]
        self.assertEqual(business.status, BLOCKED_OL)
        self.assertIn("O/L Mathematics ≥ C (you have S)", business.ol_failed)
        self.assertIn(self.course(result, "109"), result.by_group()["blocked_by_ol"])

    def test_al_mathematics_replaces_ol_maths_for_architecture(self) -> None:
        result = self.find(stream="Arts", al=["Art:B", "Mathematics:S", "Accounting:C"],
                           ol=["English:B", "Maths:S"])
        architecture = self.course(result, "023")
        self.assertEqual(architecture.decision, "eligible")
        offering = architecture.offerings[0]
        self.assertEqual(offering.status, APTITUDE)
        self.assertTrue(any("met instead by A/L Mathematics" in m for m in offering.ol_met))

    def test_missing_ol_grade_is_asked_not_guessed(self) -> None:
        result = self.find(ol=["Science:B", "English:B", "Maths:A"])
        primary = self.course(result, "137").offerings[0]
        self.assertEqual(primary.status, CHECK_OL)
        self.assertEqual(primary.ol_unknown, ["O/L Sinhala Language and Literature ≥ C"])

    def test_profile_validation(self) -> None:
        profile = StudentProfile.from_inputs(**{**STUDENT, "al": ["Combined Maths A", "Physics B", "Chemistry C"]})
        self.assertEqual(profile.al_results[0], ("Combined Mathematics", "A"))
        with self.assertRaises(ProfileError):
            StudentProfile.from_inputs(**{**STUDENT, "al": ["Cooking:A", "Physics:B", "Chemistry:C"]})
        with self.assertRaises(ProfileError):
            StudentProfile.from_inputs(**{**STUDENT, "ol": ["Science:Z"]})
        typo = self.find(admission_district="Gampah", home="Minuwangda")
        self.assertEqual((typo.profile["admission_district"], typo.origin["ds_division"]),
                         ("Gampaha", "Minuwangoda"))
        with self.assertRaisesRegex(ProfileError, "Unknown admission district"):
            self.find(admission_district="Atlantis")

    def test_admission_district_is_independent_of_home(self) -> None:
        """A student living in Minuwangoda (Gampaha) who sat the exam from a Colombo school."""

        result = self.find(admission_district="Colombo", home="Minuwangoda")
        self.assertEqual(result.profile["admission_district"], "Colombo")
        self.assertEqual((result.origin["ds_division"], result.origin["district"]), ("Minuwangoda", "Gampaha"))

    def test_interactive_reasks_until_valid(self) -> None:
        answers = iter(["Physical Science", "Combined Maths A, Physics B",               # only two -> re-ask
                        "Combined Maths A, Physics B, Chemistry C", "40",
                        "Science B, English B, Maths A", "1.56",
                        "Atlantis", "Colombo",                     # unknown district -> re-ask
                        "Minuwangda"])                             # typo fixed
        with redirect_stdout(io.StringIO()):
            profile = interactive_profile(self.finder, reader=lambda prompt: next(answers))
        self.assertEqual((profile.admission_district, profile.home, profile.z_score),
                         ("Colombo", "Minuwangoda", 1.56))

    def test_cli_json(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            main(["--stream", "Physical Science", "--al", "Combined Mathematics:A", "--al", "Physics:B",
                  "--al", "Chemistry:C", "--cgt", "40", "--admission-district", "Gampaha", "--home", "Minuwangoda",
                  "--ol", "Science:B", "--ol", "English:B", "--ol", "Maths:A", "--json"])
        data = json.loads(out.getvalue())
        self.assertEqual(data["counts"]["not_eligible"], 71)
        self.assertEqual(data["counts"]["can_apply"] + data["counts"]["with_conditions"], 55)


if __name__ == "__main__":
    unittest.main()
