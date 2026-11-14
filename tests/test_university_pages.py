"""University-website agent: domains, filtering, cleaning, passages, cache. No network (fake search client)."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from campusyamu.web.university_pages import (UniversityPages, UniversityPageStore, _clean, _resolve, domain_ok,
                                             load_domains)

COURSE = {"uni_code": "135A", "course_code": "135", "course_name": "Artificial Intelligence",
          "university": "University of Moratuwa"}
DOMAINS = {"University of Moratuwa": ["uom.lk", "mrt.ac.lk"]}

PAGE = """[Home](https://uom.lk) | [About](https://uom.lk/about) | [Contact](https://uom.lk/contact)

# BSc (Hons) in Artificial Intelligence

The degree runs for four years in the Faculty of Information Technology. Students take machine learning,
computer vision, natural language processing and robotics, with a six-month industrial training in year three.

## Facilities

Students use the GPU computing lab and the robotics lab, open on weekdays.

![logo](https://uom.lk/logo.png)
"""


@dataclass
class Doc:
    url: str
    title: str
    markdown: str
    description: str = ""
    domain: str = ""


class FakeCrawler:
    def __init__(self, docs):
        self.docs, self.queries = docs, []

    def search_documents(self, query, limit):
        self.queries.append(query)
        return self.docs[:limit]


def agent(tmp: str, docs) -> tuple[UniversityPages, FakeCrawler]:
    crawler = FakeCrawler(docs)
    return UniversityPages(UniversityPageStore(Path(tmp)), DOMAINS, lambda: crawler, enabled=True), crawler


class UniversityPagesTests(unittest.TestCase):
    def test_owner_domain_file_covers_every_institution(self) -> None:
        from campusyamu.knowledge_graph.build_graph import load_graph

        domains = load_domains()
        institutions = {a["name"] for _, a in load_graph().nodes(data=True) if a["type"] == "Institution"}
        self.assertEqual(set(domains), institutions)
        self.assertTrue(all(d and "/" not in d and not d.startswith("www.") for v in domains.values() for d in v))

    def test_domain_filter_includes_subdomains_only(self) -> None:
        self.assertTrue(domain_ok("https://itfac.mrt.ac.lk/ai", ["mrt.ac.lk"]))
        self.assertTrue(domain_ok("https://www.uom.lk/x", ["uom.lk"]))
        self.assertFalse(domain_ok("https://fakemrt.ac.lk/x", ["mrt.ac.lk"]))
        self.assertFalse(domain_ok("https://uom.lk.evil.com/x", ["uom.lk"]))

    def test_clean_drops_menus_and_images(self) -> None:
        text = _clean(PAGE)
        self.assertNotIn("Contact", text)
        self.assertNotIn("logo", text)
        self.assertIn("six-month industrial training", text)

    def test_fetch_limits_the_search_and_drops_other_sites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pages, crawler = agent(tmp, [Doc("https://itfac.mrt.ac.lk/ai", "BSc AI", PAGE, domain="itfac.mrt.ac.lk"),
                                         Doc("https://someblog.com/uom-ai", "Blog", PAGE, domain="someblog.com")])
            record = pages.fetch(COURSE)
            self.assertEqual(crawler.queries[0].include_domains, ("uom.lk", "mrt.ac.lk"))
            self.assertIn("Artificial Intelligence", crawler.queries[0].text)
            self.assertEqual([p["url"] for p in record["pages"]], ["https://itfac.mrt.ac.lk/ai"])
            saved = json.loads((Path(tmp) / "135A.json").read_text())
            self.assertEqual(saved["domains"], ["uom.lk", "mrt.ac.lk"])

    def test_cache_and_keyword_passages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pages, crawler = agent(tmp, [Doc("https://uom.lk/ai", "BSc AI", PAGE, domain="uom.lk")])
            record = pages.fetch(COURSE)
            self.assertEqual(pages.store.get("135A")["pages"], record["pages"])      # cached for the chat
            self.assertEqual(len(crawler.queries), 1)
            [best, *_] = UniversityPages.passages(record, "is there a robotics lab?", COURSE["course_name"])
            self.assertIn("robotics lab", best["text"])
            self.assertEqual(best["url"], "https://uom.lk/ai")

    def test_unavailable_without_domain_or_when_switched_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pages, crawler = agent(tmp, [])
            self.assertIn("no official website on file",
                          pages.unavailable_reason({**COURSE, "university": "Unknown University"}))
            self.assertIsNone(pages.unavailable_reason(COURSE))
            off = UniversityPages(UniversityPageStore(Path(tmp)), DOMAINS, lambda: crawler, enabled=False)
            self.assertIn("turned off", off.unavailable_reason(COURSE))
            self.assertEqual(crawler.queries, [])

    def test_resolve_loose_names(self) -> None:
        offering = _resolve("artificial intelligence", "Moratuwa")
        self.assertEqual((offering["course_name"], offering["university"]),
                         ("Artificial Intelligence", "University of Moratuwa"))
        self.assertTrue(offering["uni_code"])


class UniversityPagesLLMTests(unittest.TestCase):
    """The LLM step with a fake model: requests are well formed, unknown sources are dropped, profile is cached."""

    def test_prompt_asks_for_the_applicant_fields(self) -> None:
        from campusyamu.prompts.university import WEBSITE_PROFILE_SYSTEM

        for field in self.module.PROFILE_FIELDS:
            self.assertIn(f"    {field} ", WEBSITE_PROFILE_SYSTEM)
        self.assertIn("postgraduate", WEBSITE_PROFILE_SYSTEM)


    def setUp(self) -> None:
        from unittest import mock

        import campusyamu.web.university_pages as module

        self.module, self.calls = module, []
        self.record = {"uni_code": "135A", "domains": ["uom.lk"], "fetched_at": "2026-11-14T00:00:00+00:00",
                       "pages": [{"url": "https://uom.lk/ai", "title": "BSc AI", "domain": "uom.lk",
                                  "text": _clean(PAGE)}]}

        def fake(system, user, schema, name, model, max_tokens):
            self.calls.append({"system": system, "user": user, "schema": schema, "name": name})
            if name == "course_website_profile":
                return {"about_this_course": True, "relevant_pages": ["P1", "P9"],
                        "facts": [{"field": "industrial_training", "detail": "Six months in year three.",
                                   "sources": ["P1"]},
                                  {"field": "modules", "detail": "Machine learning, robotics.", "sources": ["P1"]},
                                  {"field": "fees", "detail": "Invented.", "sources": ["P9"]}],   # unknown page
                        "missing": [],
                        "specialisation_names": ["Civil Engineering", " Civil  Engineering", "Electrical Engineering"]}
            raise AssertionError(f"unexpected LLM call {name}")

        self.patch = mock.patch.object(module, "_llm", fake)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()

    def test_profile_is_cited_validated_and_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UniversityPageStore(Path(tmp))
            profile = self.module.extract_profile(self.record, COURSE, model="m", store=store)
            self.assertEqual([f["field"] for f in profile["facts"]], ["modules", "industrial_training"])  # ordered
            self.assertNotIn("fees", [f["field"] for f in profile["facts"]])   # cited a page that does not exist
            self.assertIn("fees", profile["missing"])
            self.assertEqual(profile["relevant_pages"], ["P1"])
            self.assertEqual(profile["pages"]["P1"]["url"], "https://uom.lk/ai")
            self.assertEqual(store.get("135A", fresh_only=False)["profile"]["facts"], profile["facts"])
            self.assertEqual(profile["version"], self.module.PROFILE_VERSION)
            self.assertEqual(profile["specialisation_names"], ["Civil Engineering", "Electrical Engineering"])
        call = self.calls[0]
        self.assertIn("untrusted evidence", call["system"])
        self.assertEqual(call["user"]["pages"][0]["id"], "P1")
        self.assertEqual(call["schema"]["properties"]["facts"]["items"]["properties"]["sources"]["items"]["enum"],
                         ["P1"])

    def test_no_pages_no_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = {**self.record, "pages": []}
            profile = self.module.extract_profile(empty, COURSE, model="m", store=UniversityPageStore(Path(tmp)))
            self.assertFalse(profile["about_this_course"])
        self.assertEqual(self.calls, [])


class SpecialisationHopTests(unittest.TestCase):
    """2nd hop: one search per specialisation, official domains only; the LLM picks the page or rejects all."""

    def setUp(self) -> None:
        from unittest import mock

        import campusyamu.web.university_pages as module

        self.module, self.llm_calls = module, []
        self.record = {"uni_code": "008B", "domains": ["uom.lk", "mrt.ac.lk"], "fetched_at": "2026-11-14T00:00:00+00:00",
                       "pages": [{"url": "https://uom.lk/engineering", "title": "Engineering", "text": "x" * 200}],
                       "profile": {"specialisation_names": ["Civil Engineering", "Electrical Engineering",
                                                            "Textile Engineering", "Mining Engineering"]}}
        civil = "The Department of Civil Engineering teaches structures, geotechnics and water resources. " * 3
        self.results = {
            "Civil Engineering University of Moratuwa": [
                Doc("https://uom.lk/news/civil-award", "News: award", civil),
                Doc("https://uom.lk/pg/msc-civil", "MSc in Civil Engineering", civil),
                Doc("https://civil.mrt.ac.lk/", "Department of Civil Engineering", civil),
                Doc("https://someblog.com/civil", "Blog", civil)],
            "Electrical Engineering University of Moratuwa": [
                Doc("https://uom.lk/events/x", "Open day", "An open day for all students of the university. " * 3)],
            "Textile Engineering University of Moratuwa": [],
        }
        self.queries = []

        test = self

        class Crawler:
            def search_documents(self, query, limit):
                test.queries.append((query.text, query.include_domains))
                if query.text.startswith("Mining"):
                    raise RuntimeError("Tavily HTTP 432: quota")
                if not query.include_domains:                     # the open search
                    return [Doc("https://textile-dept.example.org/", "Textile dept", "t" * 100),
                            Doc("https://uom.lk/x", "on list", "t" * 100)]
                return test.results.get(query.text, [])

        self.crawler = Crawler()

        def fake(system, user, schema, name, model, max_tokens):
            self.llm_calls.append({"user": user, "schema": schema})
            pages = {p["url"]: p["id"] for s in user["specialisations"] for p in s["candidate_pages"]}
            return {"cards": [
                {"name": "Civil Engineering", "page": pages["https://civil.mrt.ac.lk/"],
                 "overview": "Structures, geotechnics and water.", "modules": "Structures", "facilities": "",
                 "careers": ""},
                {"name": "Electrical Engineering", "page": "none", "overview": "", "modules": "",
                 "facilities": "", "careers": ""}]}

        self.patch = mock.patch.object(module, "_llm", fake)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()

    def test_one_search_each_then_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            section = self.module.explore_specialisations(self.record, {**COURSE, "university": "University of Moratuwa"},
                                                          self.crawler, model="m", store=UniversityPageStore(Path(tmp)))
            saved = json.loads((Path(tmp) / "008B.json").read_text())["specialisations"]
        official = [q for q in self.queries if q[1]]
        first = [q[0] for q in official if not q[0].startswith("Department of")]
        retry = [q[0] for q in official if q[0].startswith("Department of")]
        self.assertEqual(sorted(first),                                  # sent in parallel: any order
                         sorted(f"{n} University of Moratuwa" for n in self.record["profile"]["specialisation_names"]))
        self.assertEqual(sorted(retry), ["Department of Electrical Engineering University of Moratuwa",
                                         "Department of Textile Engineering University of Moratuwa"])  # not Mining:
        self.assertTrue(all(q[1] == ("uom.lk", "mrt.ac.lk") for q in official))                 # its search failed
        self.assertEqual([r["name"] for r in section["results"]], self.record["profile"]["specialisation_names"])
        self.assertEqual(section["source"], "website")              # AI (135) has no handbook specialisations
        by = {r["name"]: r for r in section["results"]}
        civil = by["Civil Engineering"]
        self.assertEqual(civil["state"], "found")
        self.assertEqual(civil["card"]["url"], "https://civil.mrt.ac.lk/")
        self.assertEqual(civil["candidates"][0]["url"], "https://civil.mrt.ac.lk/")      # department page ranked first
        self.assertNotIn("https://someblog.com/civil", [c["url"] for c in civil["candidates"]])
        self.assertEqual(by["Electrical Engineering"]["state"], "not_found")            # LLM rejected the only page
        self.assertEqual(by["Textile Engineering"]["state"], "not_found")
        self.assertEqual(by["Textile Engineering"]["off_list"], [{"url": "https://textile-dept.example.org/",
                                                                  "title": "Textile dept"}])   # shown, not used
        self.assertEqual(by["Mining Engineering"]["state"], "search_failed")
        self.assertEqual(saved["results"], section["results"])
        sent = self.llm_calls[0]["user"]["specialisations"]
        self.assertEqual([s["name"] for s in sent], ["Civil Engineering", "Electrical Engineering"])

    def test_retry_finds_the_department_page_and_skips_duplicates(self) -> None:
        dept = "The Department of Electronic and Telecommunication Engineering offers modules in signals. " * 3
        self.results = {
            "Electronic and Telecommunication Engineering University of Moratuwa": [
                Doc("http://uom.lk/efac/ent", "ENTC", dept), Doc("https://uom.lk/efac/ent/", "ENTC again", dept)],
            "Department of Electronic and Telecommunication Engineering University of Moratuwa": [
                Doc("https://uom.lk/efac/ent", "ENTC third time", dept),
                Doc("https://ent.uom.lk/", "Department of Electronic & Telecommunication Engineering", dept)],
        }
        calls = []

        def judge(system, user, schema, name, model, max_tokens):
            calls.append([p["url"] for s in user["specialisations"] for p in s["candidate_pages"]])
            pages = {p["url"]: p["id"] for s in user["specialisations"] for p in s["candidate_pages"]}
            if "https://ent.uom.lk/" in pages:
                return {"cards": [{"name": "Electronic and Telecommunication Engineering", "page": pages["https://ent.uom.lk/"],
                                   "reason": "the department's own site", "overview": "Signals and networks.",
                                   "modules": "", "facilities": "", "careers": ""}]}
            return {"cards": [{"name": "Electronic and Telecommunication Engineering", "page": "none",
                               "reason": "only a faculty listing", "overview": "", "modules": "", "facilities": "",
                               "careers": ""}]}

        from unittest import mock

        record = {**self.record, "profile": {"specialisation_names": ["Electronic and Telecommunication Engineering"]}}
        with mock.patch.object(self.module, "_llm", judge), tempfile.TemporaryDirectory() as tmp:
            section = self.module.explore_specialisations(record, {**COURSE, "university": "University of Moratuwa"},
                                                          self.crawler, model="m", store=UniversityPageStore(Path(tmp)))
        self.assertEqual(calls, [["http://uom.lk/efac/ent"], ["https://ent.uom.lk/"]])   # duplicates counted once
        [result] = section["results"]
        self.assertEqual(result["state"], "found")
        self.assertEqual(result["card"]["url"], "https://ent.uom.lk/")
        self.assertEqual(result["reason"], "the department's own site")
        self.assertEqual([c["url"] for c in result["candidates"]], ["http://uom.lk/efac/ent", "https://ent.uom.lk/"])
        self.assertTrue(result["candidates"][0]["chars"] > 0 and result["candidates"][0]["preview"])

    def test_card_must_use_its_own_specialisation_page(self) -> None:
        def wrong(system, user, schema, name, model, max_tokens):
            civil_page = user["specialisations"][0]["candidate_pages"][0]["id"]
            return {"cards": [{"name": "Electrical Engineering", "page": civil_page, "overview": "Wrong page.",
                               "modules": "", "facilities": "", "careers": ""}]}

        from unittest import mock

        with mock.patch.object(self.module, "_llm", wrong), tempfile.TemporaryDirectory() as tmp:
            section = self.module.explore_specialisations(self.record, {**COURSE, "university": "University of Moratuwa"},
                                                          self.crawler, model="m", store=UniversityPageStore(Path(tmp)))
        self.assertTrue(all(r["card"] is None for r in section["results"]))

    def test_cap_and_no_names(self) -> None:
        names = [f"Spec {i}" for i in range(14)]
        record = {**self.record, "profile": {"specialisation_names": names}}
        with tempfile.TemporaryDirectory() as tmp:
            store = UniversityPageStore(Path(tmp))
            section = self.module.explore_specialisations(record, COURSE, self.crawler, model="m", store=store)
            self.assertEqual(len(section["results"]), self.module.MAX_SPECIALISATIONS)
            self.assertEqual(section["skipped"], names[self.module.MAX_SPECIALISATIONS:])
            empty = self.module.explore_specialisations({**self.record, "profile": {}}, COURSE, self.crawler,
                                                        model="m", store=store)
        self.assertEqual(empty["results"], [])
        self.assertEqual(self.llm_calls, [])                   # nothing found anywhere: no LLM call


class HandbookSpecialisationTests(unittest.TestCase):
    def test_handbook_lists_per_university(self) -> None:
        from campusyamu.web.university_pages import handbook_specialisations

        moratuwa = handbook_specialisations("008", "University of Moratuwa")
        self.assertIn("Civil Engineering", moratuwa)
        self.assertIn("Biomedical Engineering", moratuwa)
        self.assertNotIn("Manufacturing & Industrial Engineering", moratuwa)          # that is Peradeniya's
        self.assertEqual(handbook_specialisations("135", "University of Moratuwa"), [])

    def test_campus_headings_and_degree_titles(self) -> None:
        from campusyamu.web.university_pages import handbook_specialisations, same_institution

        self.assertTrue(handbook_specialisations("022", "Trincomalee Campus"))        # "... of the Eastern University"
        self.assertEqual(handbook_specialisations("022", "Eastern University, Sri Lanka"), [])
        self.assertEqual(handbook_specialisations("104", "Eastern University, Sri Lanka"), [])   # only a degree title
        names = ["Trincomalee Campus", "Eastern University, Sri Lanka"]
        self.assertTrue(same_institution("Trincomalee Campus, Eastern University, Sri Lanka", "Trincomalee Campus", names))
        self.assertFalse(same_institution("Trincomalee Campus, Eastern University, Sri Lanka",
                                          "Eastern University, Sri Lanka", names))

    def test_parser_no_longer_swallows_the_other_courses_list(self) -> None:
        from campusyamu.agents.course_details import HandbookCourseIndex

        h = HandbookCourseIndex()
        for code in ("102", "103", "104"):
            for names in h.blocks_for(code)[0].specializations.values():
                self.assertNotIn("Yoga and Parapsychology", names, code)
                self.assertLessEqual(len(names), 3, code)

    def test_handbook_names_win_over_the_website(self) -> None:
        from campusyamu.web.university_pages import specialisation_names

        course = {"course_code": "008", "university": "University of Moratuwa"}
        names, source = specialisation_names({"profile": {"specialisation_names": ["Something Else"]}}, course)
        self.assertEqual(source, "handbook")
        self.assertIn("Civil Engineering", names)
        names, source = specialisation_names({"profile": {"specialisation_names": ["AI Track"]}},
                                             {"course_code": "135", "university": "University of Moratuwa"})
        self.assertEqual((names, source), (["AI Track"], "website"))


if __name__ == "__main__":
    unittest.main()
