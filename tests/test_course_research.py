"""Course research: three sub-agents in parallel. No network: fake search client, fake LLM, fake career run."""

from __future__ import annotations

import tempfile
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

import campusyamu.web.course_research as research_module
import campusyamu.web.university_pages as pages_module
from campusyamu.web.career_outlook import CareerOutlookStore
from campusyamu.web.course_research import CourseResearch
from campusyamu.web.university_pages import UniversityPages, UniversityPageStore

ENGINEERING = {"uni_code": "008B", "course_code": "008", "course_name": "Engineering",
               "university": "University of Moratuwa"}
AI = {"uni_code": "135A", "course_code": "135", "course_name": "Artificial Intelligence",
      "university": "University of Moratuwa"}
TEXT = "The department teaches its students through lectures, laboratories and an industrial placement. " * 3


@dataclass
class Doc:
    url: str
    title: str
    markdown: str = TEXT
    description: str = ""
    domain: str = "uom.lk"


class Fixture:
    """Fake crawler / LLM / career runner; `barrier` makes each sub-agent's first call wait for the others."""

    def __init__(self, parties: int) -> None:
        self.barrier = threading.Barrier(parties, timeout=5)
        self.first_spec = threading.Lock()
        self.spec_waited = False
        self.calls: list[str] = []
        self.order: list[str] = []

    def search(self, query, limit):
        self.calls.append(f"search:{query.category}:{query.text}")
        if query.category == "university_website":
            self.barrier.wait()
            return [Doc("https://uom.lk/course", "Course page")]
        if query.category == "university_specialisation":
            with self.first_spec:
                wait, self.spec_waited = not self.spec_waited, True
            if wait:
                self.barrier.wait()
            slug = query.text.split(" University")[0].casefold().replace(" ", "-").replace("&", "and")
            return [Doc(f"https://uom.lk/dept/{slug}", query.text.split(" University")[0])]
        return []

    def llm(self, system, user, schema, name, model, max_tokens):
        self.calls.append(f"llm:{name}")
        if name == "course_website_profile":
            self.order.append("profile")
            return {"about_this_course": True, "relevant_pages": ["P1"], "missing": [],
                    "facts": [{"field": "overview", "detail": "A degree.", "sources": ["P1"]}],
                    "specialisation_names": ["Robotics Track", "Data Track"]}
        self.order.append("cards")
        return {"cards": [{"name": s["name"], "page": s["candidate_pages"][0]["id"], "overview": f"{s['name']} card.",
                           "modules": "", "facilities": "", "careers": ""} for s in user["specialisations"]]}

    def career(self, course, on_progress=None):
        self.calls.append(f"career:{course}")
        self.barrier.wait()
        return {"status": "success", "generated_at": "2026-11-14T00:00:00+00:00",
                "course_analyses": [{"course": course, "overall_outlook": {"label": "positive"},
                                     "evidence_index": []}], "collection": []}


class CourseResearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.store = UniversityPageStore(root / "pages")
        self.outlooks = CareerOutlookStore(root / "careers")
        self.patches = [mock.patch.object(research_module, "missing_keys", lambda: [])]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def research(self, fx: Fixture, career=None) -> CourseResearch:
        class Crawler:
            def search_documents(self, query, limit):
                return fx.search(query, limit)

        websites = UniversityPages(self.store, {"University of Moratuwa": ["uom.lk", "mrt.ac.lk"]},
                                   lambda: Crawler(), enabled=True)
        return CourseResearch(websites, self.outlooks, career_runner=career or fx.career)

    def test_all_three_run_at_the_same_time(self) -> None:
        fx = Fixture(parties=3)                     # career + website + specialisations must all be waiting together
        with mock.patch.object(pages_module, "_llm", fx.llm):
            out = self.research(fx).run(ENGINEERING)
        states = {k: v["state"] for k, v in out["results"].items()}
        self.assertEqual(states, {"career": "done", "website": "done", "specialisations": "done"})
        section = out["results"]["specialisations"]["section"]
        self.assertEqual(section["source"], "handbook")                         # Moratuwa's 8, from the handbook
        self.assertIn("Civil Engineering", [r["name"] for r in section["results"]])
        self.assertTrue(all(r["state"] == "found" for r in section["results"]))
        saved = self.store.get("008B")
        self.assertEqual(saved["specialisations"]["results"], section["results"])  # one record, both parts
        self.assertEqual(saved["profile"]["facts"][0]["detail"], "A degree.")
        self.assertEqual(self.outlooks.get("Engineering")["analysis"]["overall_outlook"]["label"], "positive")

    def test_without_handbook_names_specialisations_wait_for_the_website(self) -> None:
        fx = Fixture(parties=2)                     # only career + website meet at the barrier
        fx.spec_waited = True                       # specialisation searches come later and must not wait
        with mock.patch.object(pages_module, "_llm", fx.llm):
            out = self.research(fx).run(AI)
        section = out["results"]["specialisations"]["section"]
        self.assertEqual(section["source"], "website")
        self.assertEqual([r["name"] for r in section["results"]], ["Robotics Track", "Data Track"])
        self.assertEqual(fx.order, ["profile", "cards"])

    def test_one_failure_does_not_stop_the_others(self) -> None:
        fx = Fixture(parties=2)

        def broken(course, on_progress=None):
            raise RuntimeError("Apify quota")

        with mock.patch.object(pages_module, "_llm", fx.llm):
            out = self.research(fx, career=broken).run(ENGINEERING)
        self.assertEqual(out["results"]["career"]["state"], "failed")
        self.assertIn("Apify quota", out["results"]["career"]["error"])
        self.assertEqual(out["results"]["website"]["state"], "done")
        self.assertEqual(out["results"]["specialisations"]["state"], "done")

    def test_second_run_is_all_cached_and_skip_works(self) -> None:
        fx = Fixture(parties=3)
        with mock.patch.object(pages_module, "_llm", fx.llm):
            self.research(fx).run(ENGINEERING)
            fx.calls.clear()
            again = self.research(fx).run(ENGINEERING)
            self.assertEqual({k: v["state"] for k, v in again["results"].items()},
                             {"career": "cached", "website": "cached", "specialisations": "cached"})
            self.assertEqual(fx.calls, [])
            only = self.research(fx).run(ENGINEERING, skip=("career", "website"))
        self.assertEqual(only["results"]["career"]["state"], "skipped")
        self.assertEqual(only["results"]["specialisations"]["state"], "cached")


if __name__ == "__main__":
    unittest.main()
