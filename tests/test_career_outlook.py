from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from web_app.career_outlook import CareerOutlookStore, CareerResearchJobs, compact, slug
from web_app.course_chat import CourseChat

RESULT = {
    "status": "success", "generated_at": "2026-11-12T10:00:00+00:00",
    "sources": {"web": "tavily", "model": "test-model"}, "input": {"horizon_years": 5},
    "collection": [{"course": "Quantity Surveying", "retained_after_deduplication": 18, "trusted_sources": 6,
                    "career_paths": ["quantity surveyor"]}],
    "course_analyses": [{"course": "Quantity Surveying", "status": "success",
                         "overall_outlook": {"label": "positive", "summary": "Solid choice."},
                         "future_swot": {"strengths": [{"finding": "Clear IQSSL/RICS ladder", "evidence_refs": ["E001"]}],
                                         "weaknesses": [], "opportunities": [], "threats": []},
                         "evidence_index": [{"evidence_id": "E001", "title": "QS jobs", "url": "https://ikman.lk/qs",
                                             "trusted": False}]}],
    "web_research": {"huge": "raw pages"},
}
COURSE = {"course_code": "011", "uni_code": "011G", "course_name": "Quantity Surveying",
          "university": "University of Moratuwa", "details_block": 0}


class CareerOutlookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CareerOutlookStore(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_compact_keeps_analysis_and_evidence_not_raw_pages(self) -> None:
        outlook = compact(RESULT, "Quantity Surveying")
        self.assertNotIn("web_research", outlook)
        self.assertEqual(outlook["evidence_index"][0]["url"], "https://ikman.lk/qs")
        self.assertEqual(outlook["analysis"]["overall_outlook"]["label"], "positive")
        self.assertNotIn("evidence_index", outlook["analysis"])
        self.store.save(outlook)
        self.assertEqual(self.store.get("Quantity Surveying")["model"], "test-model")
        self.assertEqual(slug("Arts (SP) - Mass Media"), "arts-sp-mass-media")
        self.assertIsNone(self.store.get("Law"))

    def test_background_job_saves_the_outlook(self) -> None:
        def runner(course, on_progress=None):
            on_progress({"event": "course_started", "course": course})
            return RESULT
        jobs = CareerResearchJobs(self.store, runner)
        self.assertEqual(jobs.start("Quantity Surveying"), (True, "started"))
        for _ in range(100):
            if jobs.status("Quantity Surveying")["state"] != "running":
                break
            time.sleep(0.02)
        self.assertEqual(jobs.status("Quantity Surveying")["state"], "done")
        self.assertIsNotNone(self.store.get("Quantity Surveying"))

    def test_failed_run_is_reported(self) -> None:
        def runner(course, on_progress=None):
            raise RuntimeError("search quota exceeded")
        jobs = CareerResearchJobs(self.store, runner)
        jobs.start("Law")
        for _ in range(100):
            if jobs.status("Law")["state"] != "running":
                break
            time.sleep(0.02)
        self.assertEqual(jobs.status("Law")["state"], "failed")
        self.assertIn("quota", jobs.status("Law")["message"])

    def test_chat_uses_the_outlook_as_source_c(self) -> None:
        chat = CourseChat(use_search=False, outlooks=self.store)
        before, _ = chat.sources(COURSE, "jobs?")
        self.assertNotIn("C", [x["id"] for x in before])
        self.store.save(compact(RESULT, "Quantity Surveying"))
        sources, _ = chat.sources(COURSE, "jobs?")
        career = next(s for s in sources if s["id"] == "C")
        self.assertIn("IQSSL", career["text"])
        self.assertIn("E001: QS jobs — https://ikman.lk/qs", career["text"])
        chat._call = lambda payload: {"answer": "Local QS jobs exist [C].", "sources_used": ["C"], "status": "answered"}
        answer = chat.ask("What jobs?", COURSE)
        self.assertTrue(answer["career_research"])
        self.assertFalse(answer["start_career_research"])
        self.assertEqual(answer["sources"][0]["links"][0]["url"], "https://ikman.lk/qs")


class StartOnRequestTests(unittest.TestCase):
    """Research runs only when the student asks for it in the chat."""

    @classmethod
    def setUpClass(cls) -> None:
        from web_app.server import WebApp
        cls.web = WebApp()
        cls.web.options["llm_available"] = True

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web.finder.close()

    def setUp(self) -> None:
        self.started = []
        self.web.career_jobs.start = lambda course: (self.started.append(course) or (True, "started"))
        self.web.career_jobs.status = lambda course: None

    def ask(self, flag: bool) -> dict:
        self.web.chat.ask = lambda *a, **k: {"answer": "ok", "status": "answered", "sources": [], "notes": [],
                                             "model": "m", "career_research": False,
                                             "start_career_research": flag}
        status, data = self.web.ask({"course": COURSE, "question": "q"})
        self.assertEqual(status, 200)
        return data

    def test_no_research_unless_asked(self) -> None:
        import web_app.server as server
        original = server.missing_keys
        server.missing_keys = lambda: []
        try:
            data = self.ask(False)
            self.assertEqual(self.started, [])
            self.assertNotIn("start_career_research", data)
            self.ask(True)
            self.assertEqual(self.started, ["Quantity Surveying"])
        finally:
            server.missing_keys = original


if __name__ == "__main__":
    unittest.main()
