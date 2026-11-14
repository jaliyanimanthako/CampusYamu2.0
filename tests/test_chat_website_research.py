"""The course chat and the course research: W/D sources from the cache, research started from the chat."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from campusyamu.web.career_outlook import CareerOutlookStore, CareerResearchJobs
from campusyamu.web.course_chat import CourseChat, website_sources
from campusyamu.web.university_pages import UniversityPages, UniversityPageStore

COURSE = {"course_code": "008", "uni_code": "008G", "course_name": "Engineering",
          "university": "University of Moratuwa", "details_block": 0}
RECORD = {
    "uni_code": "008G", "course_name": "Engineering", "university": "University of Moratuwa",
    "domains": ["uom.lk", "mrt.ac.lk"], "fetched_at": "2099-01-01T00:00:00+00:00", "pages": [],
    "profile": {"about_this_course": True, "generated_at": "2026-11-14T06:20:00+00:00", "version": 2,
                "facts": [{"field": "overview", "detail": "A four-year engineering degree.", "sources": ["P1"]},
                          {"field": "industrial_training", "detail": "Six months in year three.", "sources": ["P1"]}],
                "missing": ["fees"], "pages": {"P1": {"title": "Faculty of Engineering", "url": "https://uom.lk/efac"}}},
    "specialisations": {"source": "handbook", "generated_at": "2026-11-14T06:44:00+00:00", "results": [
        {"name": "Civil Engineering", "state": "found",
         "card": {"overview": "Structures and water.", "modules": "Structures", "facilities": "", "careers": "",
                  "page": "D1", "url": "https://civil.mrt.ac.lk", "title": "Department of Civil Engineering"}},
        {"name": "Electronic and Telecommunication Engineering", "state": "not_found", "card": None}]},
}


class FakeStore:
    def __init__(self, record=None) -> None:
        self.record = record

    def get(self, uni_code, fresh_only=True):
        return self.record if self.record and self.record["uni_code"] == uni_code else None


class WebsiteSourceTests(unittest.TestCase):
    def test_w_is_the_profile_and_d_the_cards(self) -> None:
        w, d = website_sources(RECORD, COURSE)
        self.assertEqual((w["id"], w["kind"], d["id"], d["kind"]), ("W", "university_website", "D", "specialisations"))
        self.assertIn("industrial training: Six months in year three. (P1)", w["text"])
        self.assertIn("not on the website: fees", w["text"])
        self.assertEqual(w["links"], [{"id": "P1", "title": "Faculty of Engineering", "url": "https://uom.lk/efac"}])
        self.assertIn("uom.lk (official website), read 2026-11-14", w["citation"])
        self.assertIn("Civil Engineering: Structures and water.", d["text"])
        self.assertIn("Electronic and Telecommunication Engineering: no department page found", d["text"])
        self.assertIn("names from the UGC handbook", d["title"])
        self.assertEqual([l["url"] for l in d["links"]], ["https://civil.mrt.ac.lk"])

    def test_nothing_cached_nothing_added(self) -> None:
        self.assertEqual(website_sources(None, COURSE), [])
        no_cards = {**RECORD, "specialisations": {"results": [{"name": "X", "card": None}]}}
        self.assertEqual([s["id"] for s in website_sources(no_cards, COURSE)], ["W"])


class ChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def chat(self, record, enabled=True) -> CourseChat:
        websites = UniversityPages(UniversityPageStore(Path(self.tmp.name)), {}, enabled=enabled)
        websites.store = FakeStore(record)
        return CourseChat(use_search=False, model="m", outlooks=CareerOutlookStore(Path(self.tmp.name)),
                          websites=websites)

    def test_sources_include_w_and_d_from_the_cache_only(self) -> None:
        sources, _ = self.chat(RECORD).sources(COURSE, "what modules?")
        self.assertEqual([s["id"] for s in sources], ["S1", "R", "W", "D"])
        sources, _ = self.chat(None).sources(COURSE, "what modules?")
        self.assertEqual([s["id"] for s in sources], ["S1", "R"])          # nothing researched: no fetch, no W
        sources, _ = self.chat(RECORD, enabled=False).sources(COURSE, "what modules?")
        self.assertEqual([s["id"] for s in sources], ["S1", "R"])          # switched off in settings

    def test_research_flag_while_something_is_missing(self) -> None:
        def ask(chat, flag):
            chat._call = lambda payload: {"answer": "ok", "status": "answered", "sources_used": [],
                                          "start_career_research": flag}
            return chat.ask("research it", COURSE)

        self.assertTrue(ask(self.chat(None), True)["start_career_research"])           # nothing researched
        self.assertFalse(ask(self.chat(None), False)["start_career_research"])          # not asked
        with_w = ask(self.chat(RECORD), True)
        self.assertTrue(with_w["website_research"])
        self.assertTrue(with_w["start_career_research"])                                # careers still missing
        outlook = {"course": "Engineering", "generated_at": "2026-11-14", "analysis": {}, "evidence_index": []}
        chat = self.chat(RECORD)
        chat.outlooks.save(outlook)
        self.assertFalse(ask(chat, True)["start_career_research"])                       # all there already


class FullResearchJobTests(unittest.TestCase):
    def test_chat_research_runs_the_course_research(self) -> None:
        from unittest import mock

        import campusyamu.web.course_research as research

        calls = []

        class FakeResearch:
            def __init__(self, websites, outlooks, career_runner=None, on_event=None):
                self.on_event = on_event

            def run(self, offering):
                calls.append(offering)
                self.on_event("website", "5 official page(s) found")
                return {"results": {"career": {"state": "cached"}, "website": {"state": "done"},
                                    "specialisations": {"state": "done"}}}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(research, "CourseResearch", FakeResearch):
            websites = UniversityPages(UniversityPageStore(Path(tmp)), {}, enabled=True)
            jobs = CareerResearchJobs(CareerOutlookStore(Path(tmp)), websites=websites)
            self.assertEqual(jobs.start("Engineering", COURSE), (True, "started"))
            for _ in range(100):
                if jobs.status("Engineering")["state"] != "running":
                    break
                time.sleep(0.02)
        job = jobs.status("Engineering")
        self.assertEqual((job["state"], job["scope"]), ("done", "course"))
        self.assertEqual(job["parts"], {"career": "cached", "website": "done", "specialisations": "done"})
        self.assertEqual(calls[0]["uni_code"], "008G")

    def test_without_an_offering_or_when_off_it_is_career_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            off = UniversityPages(UniversityPageStore(Path(tmp)), {}, enabled=False)
            jobs = CareerResearchJobs(CareerOutlookStore(Path(tmp)), runner=lambda c, on_progress=None: {
                "status": "success", "course_analyses": [{"course": c}], "collection": []}, websites=off)
            jobs.start("Engineering", COURSE)
            self.assertEqual(jobs.status("Engineering")["scope"], "career")
            for _ in range(100):
                if jobs.status("Engineering")["state"] != "running":
                    break
                time.sleep(0.02)


if __name__ == "__main__":
    unittest.main()
