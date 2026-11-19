"""Course research: one web agent with three sub-agents running in parallel.

For one offering (a course at a university):

  career            the career-trends agent (agents.career_trends): web + Reddit search, research
                    agent, cited 5-year SWOT. Per COURSE (shared by every university), cached in
                    data/cache/career_outlooks/. Takes minutes.
  website           the university-website agent (university_pages): one search on the university's
                    official domains, then the LLM reads the pages into the applicant profile.
  specialisations   one search per specialisation on the official domains (in parallel), then the
                    LLM writes a card each. The names come from the UGC handbook for this university,
                    so this starts at once alongside the other two; only when the handbook lists none
                    does it wait for the website profile and use the names found there.

Website and specialisations are per OFFERING, cached together in
data/cache/university_pages/<uni_code>.json. Everything cached is reused unless refresh=True,
so a second run costs nothing. Every sub-agent reports its own state; one failing does not
stop the others.

    uv run python -m campusyamu.web.course_research --course Engineering --university Moratuwa
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from .career_outlook import CareerOutlookStore, compact, missing_keys, run_research
from .university_pages import (PROFILE_VERSION, SPECIALISATION_VERSION, UniversityPages, explore_specialisations,
                               extract_profile, handbook_specialisations)

SUBAGENTS = ("career", "website", "specialisations")


class CourseResearch:
    def __init__(self, websites: UniversityPages | None = None, outlooks: CareerOutlookStore | None = None,
                 career_runner: Callable[..., dict[str, Any]] = run_research,
                 on_event: Callable[[str, str], None] | None = None, handbook=None) -> None:
        self.websites = websites or UniversityPages(enabled=True)
        self.outlooks = outlooks or CareerOutlookStore()
        self.career_runner = career_runner
        self.on_event = on_event or (lambda agent, message: None)
        self.handbook = handbook
        self._lock = threading.Lock()

    def _emit(self, agent: str, message: str) -> None:
        with self._lock:
            self.on_event(agent, message)

    # --- sub-agents ---------------------------------------------------------------------------------
    def _career(self, offering: dict[str, Any], refresh: bool) -> dict[str, Any]:
        course = offering["course_name"]
        if not refresh and (outlook := self.outlooks.get(course)):
            return {"state": "cached", "outlook": outlook}
        if missing := missing_keys():
            return {"state": "skipped", "reason": "needs " + ", ".join(missing)}
        self._emit("career", f"web + Reddit research for {course!r} started (takes minutes)")

        def progress(event: dict[str, Any]) -> None:
            detail = event.get("query") or event.get("category") or event.get("status") or ""
            self._emit("career", f"{str(event.get('event', '')).replace('_', ' ')}"
                                 f"{': ' + str(detail)[:70] if detail else ''}")

        result = self.career_runner(course, on_progress=progress)
        if result.get("status") == "failed":
            raise RuntimeError("the career pipeline failed (see the log above)")
        outlook = compact(result, course)
        self.outlooks.save(outlook)
        return {"state": "done", "outlook": outlook}

    def _website(self, offering: dict[str, Any], cached: dict[str, Any] | None, refresh: bool) -> dict[str, Any]:
        if reason := self.websites.unavailable_reason(offering):
            return {"state": "skipped", "reason": reason, "record": cached}
        profile = (cached or {}).get("profile") or {}
        if not refresh and cached and profile.get("version") == PROFILE_VERSION:
            return {"state": "cached", "record": cached}
        record = cached if (cached and not refresh) else None
        if record is None:
            self._emit("website", f"searching {', '.join(self.websites.domains_for(offering['university']))}")
            record = self.websites.fetch(offering)
            self._emit("website", f"{len(record['pages'])} official page(s) found; reading them")
        extract_profile(record, offering, store=self.websites.store)
        return {"state": "done", "record": record}

    def _specialisations(self, offering: dict[str, Any], cached: dict[str, Any] | None, refresh: bool,
                         website: Future) -> dict[str, Any]:
        if reason := self.websites.unavailable_reason(offering):
            return {"state": "skipped", "reason": reason}
        names = handbook_specialisations(offering.get("course_code"), offering["university"], self.handbook)
        source = "handbook"
        section = (cached or {}).get("specialisations") or {}
        if (not refresh and names and section.get("version") == SPECIALISATION_VERSION
                and section.get("source") == "handbook" and [r["name"] for r in section["results"]]
                == names[:len(section["results"])]):
            return {"state": "cached", "section": section}
        if names:                               # from the handbook: no need to wait for the website
            record = {"domains": self.websites.domains_for(offering["university"]), "pages": []}
        else:
            self._emit("specialisations", "none in the handbook; waiting for the website profile")
            outcome = website.result()
            record = outcome.get("record") or {}
            names = (record.get("profile") or {}).get("specialisation_names") or []
            source = "website"
            if not names:
                return {"state": "skipped", "reason": "no specialisations in the handbook or on the website"}
            if not refresh and section.get("version") == SPECIALISATION_VERSION and section.get("source") == "website":
                return {"state": "cached", "section": section}
        self._emit("specialisations", f"{len(names)} from the {source}: one search each, in parallel")
        section = explore_specialisations(record, offering, self.websites.crawler(), names=names, source=source,
                                          save=False)
        found = sum(r["state"] == "found" for r in section["results"])
        self._emit("specialisations", f"{found} of {len(section['results'])} found on the official site")
        return {"state": "done", "section": section}

    # --- the run --------------------------------------------------------------------------------------
    def run(self, offering: dict[str, Any], refresh: bool = False, skip: tuple[str, ...] = ()) -> dict[str, Any]:
        """All three sub-agents in parallel; returns their states and outputs, and saves the website cache."""

        started = time.perf_counter()
        cached = self.websites.store.get(offering["uni_code"])
        timings: dict[str, float] = {}

        def timed(name: str, fn: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
            t0 = time.perf_counter()
            try:
                out = fn(*args)
            except Exception as exc:                        # one sub-agent failing does not stop the others
                out = {"state": "failed", "error": str(exc)[:300]}
            timings[name] = time.perf_counter() - t0
            self._emit(name, f"{out['state']} ({timings[name]:.1f} s)"
                             + (f": {out.get('reason') or out.get('error')}" if out.get("reason") or out.get("error")
                                else ""))
            return out

        skipped = {"state": "skipped", "reason": "not requested"}
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="course-research") as pool:
            career = pool.submit(timed, "career", self._career, offering, refresh) if "career" not in skip else None
            website = (pool.submit(timed, "website", self._website, offering, cached, refresh)
                       if "website" not in skip else None)
            if website is None:                             # specialisations may need its result: a done stand-in
                website = Future()
                website.set_result({"state": "skipped", "record": cached})
            specs = (pool.submit(timed, "specialisations", self._specialisations, offering, cached, refresh, website)
                     if "specialisations" not in skip else None)
            results = {"career": career.result() if career else skipped,
                       "website": website.result() if "website" not in skip else skipped,
                       "specialisations": specs.result() if specs else skipped}

        # one write for the offering: the website record plus the specialisation section
        record = results["website"].get("record") or cached
        if record and results["specialisations"].get("state") == "done":
            record["specialisations"] = results["specialisations"]["section"]
            self.websites.store.save(record)
        return {"offering": offering, "results": results, "timings": timings,
                "wall_seconds": time.perf_counter() - started, "record": record}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    from .university_pages import _resolve, format_profile, format_specialisations

    parser = argparse.ArgumentParser(
        description="Research one course at one university with three sub-agents in parallel: career trends "
                    "(web + Reddit), the university's official website, and its specialisations.",
        epilog="e.g.  uv run python -m campusyamu.web.course_research --course Engineering --university Moratuwa")
    parser.add_argument("--course", required=True, help="course name, loosely spelt")
    parser.add_argument("--university", required=True, help='university name, loosely spelt (e.g. "Moratuwa")')
    parser.add_argument("--refresh", action="store_true", help="ignore every cache and research again")
    parser.add_argument("--skip", action="append", choices=SUBAGENTS, default=[],
                        help="leave out a sub-agent (repeatable), e.g. --skip career")
    args = parser.parse_args(argv)
    _load_env(None)

    offering = _resolve(args.course, args.university)
    print(f"course     : {offering['course_name']}  ({offering['uni_code']})  at {offering['university']}")
    print(f"sub-agents : {', '.join(a for a in SUBAGENTS if a not in args.skip)}  (in parallel; cached results reused)\n")

    def event(agent: str, message: str) -> None:
        print(f"  [{time.strftime('%H:%M:%S')}] {agent:<16} {message}", flush=True)

    research = CourseResearch(on_event=event)
    out = research.run(offering, refresh=args.refresh, skip=tuple(args.skip))
    results, timings = out["results"], out["timings"]
    total = sum(timings.values())
    print(f"\nwall time  : {out['wall_seconds']:.1f} s   (the sub-agents' times add up to {total:.1f} s)")

    career = results["career"]
    print(f"\n=== career trends ({career['state']}) ===")
    if career.get("outlook"):
        overall = (career["outlook"].get("analysis") or {}).get("overall_outlook") or {}
        print(f"  outlook    {overall.get('label', '-')}  (confidence {overall.get('confidence', '-')}, "
              f"{len(career['outlook'].get('evidence_index', []))} sources, {career['outlook'].get('generated_at', '')[:10]})")
        if overall.get("summary"):
            print(f"  summary    {overall['summary']}")
    elif career.get("reason") or career.get("error"):
        print(f"  {career.get('reason') or career.get('error')}")

    website = results["website"]
    print(f"\n=== university website ({website['state']}) ===")
    profile = (out["record"] or {}).get("profile")
    if profile:
        print("\n".join(format_profile(profile)))
    elif website.get("reason") or website.get("error"):
        print(f"  {website.get('reason') or website.get('error')}")

    specs = results["specialisations"]
    print(f"\n=== specialisations ({specs['state']}"
          + (f", names from the {specs['section']['source']}" if specs.get("section") else "") + ") ===")
    if specs.get("section"):
        print("\n".join(format_specialisations(specs["section"])))
    elif specs.get("reason") or specs.get("error"):
        print(f"  {specs.get('reason') or specs.get('error')}")
    return 0 if all(r["state"] != "failed" for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
