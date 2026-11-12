from __future__ import annotations

import unittest

from course_details import HandbookCourseIndex
from course_finder.finder import CourseFinder
from RAG_Agent.graph_pipeline.build_graph import load_graph
from student_pipeline.graph import build_pipeline, run_pipeline


class HandbookIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = HandbookCourseIndex()
        cls.courses = {a["code"]: a["name"] for _, a in load_graph().nodes(data=True) if a["type"] == "Course"}

    def test_every_course_has_its_handbook_block(self) -> None:
        missing = [name for code, name in self.courses.items() if not self.index.blocks_for(code)]
        self.assertEqual(missing, [])
        for code in self.courses:
            for block in self.index.blocks_for(code):
                self.assertIn(code, block.codes)
                self.assertTrue(block.section.startswith("2.2"), (code, block.section))
                self.assertTrue(block.pages and block.passage_ids, code)        # citation + vector-DB passages

    def test_card_fields(self) -> None:
        ai = self.index.blocks_for("117")[0]
        self.assertEqual((ai.section, ai.pages), ("2.2.4.11", [82]))
        self.assertEqual(ai.degree_programmes, ["Bachelor of Science Honours in Artificial Intelligence [BScHons (AI)]"])
        self.assertEqual((ai.duration, ai.medium), (["4 years"], ["English"]))
        qs = self.index.blocks_for("011")[0]                                    # label and value on separate lines
        self.assertEqual(qs.duration, ["4 years"])
        self.assertEqual(self.index.blocks_for("001")[0].duration, ["5 years"])   # "Duration: 05 Years"
        architecture = self.index.blocks_for("023")[0]
        self.assertTrue(any("Aptitude Test" in n for n in architecture.notes))
        engineering = self.index.blocks_for("008")[0]
        self.assertIn("Biomedical Engineering", engineering.specializations["University of Moratuwa"])
        self.assertFalse(any(n == "Biomedical Engineering" for n in engineering.notes))
        tesl = self.index.blocks_for("105")[0]                                  # prose: "conducted only in English Medium"
        self.assertEqual(tesl.medium, ["English"])

    def test_arts_courses_have_one_block_per_university(self) -> None:
        music = self.index.blocks_for("068")
        self.assertEqual(len(music), 4)
        self.assertEqual(self.index.block_for_offering("068", "University of Jaffna"), 1)
        self.assertEqual(self.index.block_for_offering("068", "University of the Visual & Performing Arts"), 0)
        self.assertEqual(self.index.block_for_offering("068", "Eastern University",
                                                       "Swamy Vipulananda Institute of Aesthetic Studies, Kallady"), 2)
        self.assertIsNone(self.index.block_for_offering("068", "Somewhere Else"))
        self.assertEqual(self.index.block_for_offering("117", "University of Moratuwa"), 0)
        self.assertEqual(music[1].medium, ["Tamil"])
        mass_media = self.index.blocks_for("020")[0]                           # "(Course Codes : Mass Media - 020; ...)"
        self.assertEqual((mass_media.duration, mass_media.medium), (["4 years"], ["Sinhala"]))


class PipelineDetailsTests(unittest.TestCase):
    def test_report_has_details_for_every_row(self) -> None:
        finder = CourseFinder()
        try:
            app = build_pipeline(finder, use_llm=False)
            report = run_pipeline(dict(stream="Arts", al=["Music:A", "Sinhala:B", "Dance:C"], cgt=40,
                                       admission_district="Colombo", home="Colombo", ol=[], z_score=1.2,
                                       preferences="music"), app)["report"]
        finally:
            finder.close()
        rows = [r for band in report["bands"].values() for r in band]
        details = report["course_details"]
        self.assertTrue(all(details[r["course_code"]]["blocks"] for r in rows))
        jaffna = next(r for r in rows if r["uni_code"] == "068E")
        block = details["068"]["blocks"][jaffna["details_block"]]
        self.assertIn("University of Jaffna", block["title"])
        first = report["rankings"]["distance"]["suggestions"][0]
        self.assertIn(first["course_code"], details)
        self.assertIn("course_details", set(app.get_graph().nodes))


if __name__ == "__main__":
    unittest.main()
