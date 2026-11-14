"""'Ask about this course': answer a student's question about one course.

Context for each question (numbered sources the answer must cite):

* S1..   the course's own handbook section, found by course code
         (course_details; for Arts courses offered in several places, the
         block for this university);
* R      the student's own facts for this course from the pipeline report
         (band, cut-off, margin, travel, O/L status, ranking position, ...);
* H1..   wider handbook passages from the hybrid search (BM25 + vector +
         optional reranker in Neo4j) for general questions, e.g. how
         aptitude tests or applications work. Skipped with a note when Neo4j
         is not reachable.
* C      the course's career outlook from the web agent (agents.career_trends),
         when it has been researched: career paths, a cited 5-year SWOT,
         local vs overseas, further study, with its evidence list (E001 ...
         -> title and URL). Cached per course (career_outlook.py).
* W      what the university's official website says about this course
         (university_pages.py): the applicant profile the LLM wrote from the
         pages (overview, faculty, modules, specialisations, training, ...),
         each fact with its page link;
* D      a card per specialisation from its department's page, with links.
         W and D come from the course research (course_research.py), started
         in the chat when the student asks for research, cached per offering;
         the chat only reads the cache, it never fetches while answering.

One OpenAI Responses call per question (strict JSON). The model may only cite
the sources given; unknown ids are dropped.

Memory: with a user_id (a signed-in student) the server keeps the chat
(campusyamu.memory): the student's facts, this chat's running summary and the
newest turns go into the prompt, a follow-up is rewritten to stand alone for the
handbook search, and the turn is saved. Without a user_id the caller sends the
earlier turns as `history` (the last chat.history_turns are used).

Scope (web/guardrail.py): a Gemini Decision check runs alongside the recall, the
rewrite and the search; a message outside the course / selection-process domain
gets a fixed refusal (status out_of_scope) with no answer call and nothing saved.
The chat prompt has its own scope rules as a second layer.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from campusyamu.core import settings

from campusyamu.agents.course_details import HandbookCourseIndex
from campusyamu.core.openai_client import call_structured

from campusyamu.memory import ChatMemory
from campusyamu.prompts import guardrail as guard_prompts

from .career_outlook import CareerOutlookStore
from .guardrail import ScopeGuard, Verdict
from .university_pages import UniversityPages
from campusyamu.prompts.course_chat import COURSE_CHAT_SYSTEM as SYSTEM_PROMPT

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
MAX_QUESTION = 1000
STATUSES = ("answered", "partly_answered", "not_in_sources", "out_of_scope")
MAX_HISTORY_TURNS = settings.get("chat.history_turns", 8)
MAX_HISTORY_CHARS = 1500
MAX_SECTION_CHARS = 7000
MAX_CAREER_CHARS = 9000
CAREER_FIELDS = ("overall_outlook", "course_introduction", "future_swot", "local_vs_overseas", "further_study",
                 "niche_specialisations", "limitations")
SEARCH_HITS = settings.get("chat.search_hits", 4)
SEARCH_RETRY_SECONDS = 60
REPORT_FIELDS = (
    "uni_code", "course_name", "university", "site", "band", "predicted_cutoff", "uncertainty",
    "latest_cutoff", "latest_year", "expected_margin", "years_met", "years_compared",
    "historical_alignment", "evidence_confidence", "zscore_note", "car_min", "bus_min_est", "road_km",
    "status", "ol_met", "ol_failed", "ol_unknown", "aptitude_test", "preference_score",
    "preference_marks", "order3_position", "order3_note", "parts",
)


def _trim(value: Any, limit: int = 600) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= limit else text[:limit] + "…"


def website_sources(record: dict[str, Any] | None, course: dict[str, Any]) -> list[dict[str, Any]]:
    """W (the website profile) and D (the specialisation cards) from the cached course research."""

    if not record:
        return []
    out = []
    domain = (record.get("domains") or ["university website"])[0]
    university = course.get("university") or record.get("university")
    profile = record.get("profile") or {}
    if profile.get("facts"):
        pages = profile.get("pages") or {}
        lines = [f"{f['field'].replace('_', ' ')}: {f['detail']} ({', '.join(f['sources'])})" for f in profile["facts"]]
        if profile.get("missing"):
            lines.append("not on the website: " + ", ".join(m.replace("_", " ") for m in profile["missing"]))
        if not profile.get("about_this_course"):
            lines.insert(0, "(none of the pages is clearly about this course; these may be faculty facts)")
        lines.append("pages: " + "; ".join(f"{pid} = {p['url']}" for pid, p in pages.items()))
        out.append({"id": "W", "kind": "university_website",
                    "title": f"{university} website: {course.get('course_name') or record.get('course_name')}",
                    "citation": f"{domain} (official website), read {str(profile.get('generated_at', ''))[:10]}",
                    "text": "\n".join(lines)[:MAX_SECTION_CHARS],
                    "links": [{"id": pid, "title": p["title"], "url": p["url"]} for pid, p in pages.items()]})
    section = record.get("specialisations") or {}
    results = section.get("results") or []
    if any(r.get("card") for r in results):
        lines, links = [], []
        for r in results:
            card = r.get("card")
            if card:
                parts = [card["overview"]] + [f"{k}: {card[k]}" for k in ("modules", "facilities", "careers")
                                              if card.get(k)]
                lines.append(f"{r['name']}: " + " | ".join(parts) + f" (page {card['url']})")
                links.append({"id": r["name"], "title": f"{r['name']}: {card['title']}", "url": card["url"]})
            else:
                lines.append(f"{r['name']}: no department page found on the official website")
        names_from = {"handbook": "the UGC handbook", "website": "the university website"}.get(
            section.get("source"), "the research")
        out.append({"id": "D", "kind": "specialisations",
                    "title": f"Specialisations at {university} (names from {names_from})",
                    "citation": f"{domain} department pages, read {str(section.get('generated_at', ''))[:10]}",
                    "text": "\n".join(lines)[:MAX_SECTION_CHARS], "links": links})
    return out


class CourseChat:
    def __init__(self, handbook: HandbookCourseIndex | None = None, model: str | None = None,
                 use_search: bool = True, outlooks: CareerOutlookStore | None = None,
                 websites: UniversityPages | None = None, memory: ChatMemory | None = None,
                 guard: ScopeGuard | None = None) -> None:
        self.handbook = handbook or HandbookCourseIndex()
        self.memory = memory
        self.guard = guard                              # None: no scope check (the prompt's rules only)
        self._pool: ThreadPoolExecutor | None = None
        self.outlooks = outlooks or CareerOutlookStore()
        self.websites = websites
        self.model = model or settings.model("chat", DEFAULT_MODEL)
        self.use_search = use_search
        self._retriever = None
        self._driver = None
        self._search_error: str | None = None
        self._search_failed_at = 0.0

    # --- handbook search (optional) ------------------------------------------------
    def retriever(self):
        """The hybrid retriever, or None (with a reason) when Neo4j/OpenAI isn't available."""

        if not self.use_search:
            self._search_error = "handbook search disabled"
            return None
        if self._retriever is not None:
            return self._retriever
        if time.time() - self._search_failed_at < SEARCH_RETRY_SECONDS:
            return None
        try:
            from campusyamu.handbook_search.embeddings import OpenAIEmbedder
            from campusyamu.handbook_search.retriever import CrossEncoderReranker, HybridRetriever
            from campusyamu.handbook_search.store import HandbookStore, connect

            driver = connect()
            driver.verify_connectivity()
            try:
                reranker = CrossEncoderReranker()
            except Exception:                                   # optional extra not installed
                reranker = None
            self._driver = driver
            self._retriever = HybridRetriever(HandbookStore(driver, os.getenv("NEO4J_DATABASE")),
                                              OpenAIEmbedder(), reranker)
            self._search_error = None
            return self._retriever
        except BaseException as exc:                            # connect() raises SystemExit on missing config
            if isinstance(exc, KeyboardInterrupt):
                raise
            self._search_failed_at = time.time()
            self._search_error = f"handbook search unavailable ({str(exc)[:120] or type(exc).__name__})"
            return None

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
        if self.memory is not None:
            self.memory.close()
        if self._pool is not None:
            self._pool.shutdown(wait=False)

    # --- one question ------------------------------------------------------------------
    def sources(self, course: dict[str, Any], question: str) -> tuple[list[dict[str, Any]], list[str]]:
        """The numbered sources; `question` is only used for the handbook search (H)."""

        notes: list[str] = []
        code = str(course.get("course_code") or "")
        blocks = self.handbook.blocks_for(code)
        index = course.get("details_block")
        chosen = [blocks[index]] if isinstance(index, int) and 0 <= index < len(blocks) else blocks
        sources: list[dict[str, Any]] = []
        own_passages: set[str] = set()
        for i, block in enumerate(chosen, 1):
            own_passages |= set(block.passage_ids)
            text = block.text if len(block.text) <= MAX_SECTION_CHARS else block.text[:MAX_SECTION_CHARS] + "…"
            sources.append({"id": f"S{i}", "kind": "course_section", "title": block.title,
                            "citation": block.citation, "text": text})
        if not chosen:
            notes.append("no handbook section found for this course")
        facts = {k: course[k] for k in REPORT_FIELDS if course.get(k) not in (None, "", [])}
        sources.append({"id": "R", "kind": "student_report", "title": "Your results for this course",
                        "citation": "CampusYamu report", "text": json.dumps(facts, ensure_ascii=False, default=str)})
        outlook = self.outlooks.get(str(course.get("course_name") or ""))
        if outlook:
            analysis = {k: outlook["analysis"].get(k) for k in CAREER_FIELDS if outlook["analysis"].get(k)}
            text = json.dumps(analysis, ensure_ascii=False, default=str)
            if len(text) > MAX_CAREER_CHARS:
                text = text[:MAX_CAREER_CHARS] + "…"
            evidence = "\n".join(f"{e.get('evidence_id')}: {e.get('title')} — {e.get('url')}"
                                 + (" (trusted)" if e.get("trusted") else "")
                                 for e in outlook.get("evidence_index", []))
            sources.append({"id": "C", "kind": "career_outlook",
                            "title": f"Career research: {outlook['course']} ({outlook.get('region', 'Sri Lanka')})",
                            "citation": f"web research, {str(outlook.get('generated_at', ''))[:10]}",
                            "text": f"{text}\n\nEvidence:\n{evidence}",
                            "links": [{"id": e.get("evidence_id"), "title": e.get("title"), "url": e.get("url")}
                                      for e in outlook.get("evidence_index", []) if e.get("url")]})
        if self.websites is not None and self.websites.enabled:      # chat.website.enabled in settings.yaml
            sources += website_sources(self.websites.store.get(str(course.get("uni_code") or "")), course)
        retriever = self.retriever()
        if retriever is None:
            notes.append(self._search_error or "handbook search unavailable")
        else:
            try:
                hits = retriever.search(f"{course.get('course_name', '')}: {question}", k=SEARCH_HITS + len(own_passages))
            except Exception as exc:
                hits = []
                notes.append(f"handbook search failed ({str(exc)[:120]})")
            extra = [h for h in hits if h.passage_id not in own_passages][:SEARCH_HITS]
            for i, hit in enumerate(extra, 1):
                sources.append({"id": f"H{i}", "kind": "handbook_search", "title": hit.title,
                                "citation": hit.citation, "text": hit.text[:3000]})
        return sources, notes

    def request_payload(self, question: str, course: dict[str, Any], student: dict[str, Any],
                        history: list[dict[str, str]], sources: list[dict[str, Any]],
                        memory: dict[str, Any] | None = None, trim_history: bool = True) -> dict[str, Any]:
        """trim_history=False: the turns come from memory, already cut to its token budget."""

        turns = []
        for turn in history[-MAX_HISTORY_TURNS:] if trim_history else history:
            if turn.get("role") in ("user", "assistant") and str(turn.get("content", "")).strip():
                content = str(turn["content"])
                turns.append({"role": turn["role"], "content": content[:MAX_HISTORY_CHARS] if trim_history else content})
        context = {
            "course": f"{course.get('course_name')} ({course.get('uni_code')}) — {course.get('university')}",
            "student": {k: _trim(v) for k, v in student.items()},
            "sources": [{k: s[k] for k in ("id", "title", "citation", "text")} for s in sources],
        }
        if memory:
            context["memory"] = memory
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["answer", "sources_used", "status", "start_career_research"],
            "properties": {
                "start_career_research": {"type": "boolean"},
                "answer": {"type": "string"},
                "sources_used": {"type": "array", "items": {"type": "string", "enum": [s["id"] for s in sources]}},
                "status": {"type": "string", "enum": list(STATUSES)},
            },
        }
        return {
            "model": self.model, "store": False, "max_output_tokens": 1500,
            "input": [{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "system", "content": "Context:\n" + json.dumps(context, ensure_ascii=False, default=str)},
                      *turns, {"role": "user", "content": question}],
            "text": {"format": {"type": "json_schema", "name": "course_answer", "strict": True, "schema": schema}},
        }

    def _refusal(self, question: str, course: dict[str, Any], verdict: Verdict, notes: list[str],
                 search_question: str) -> dict[str, Any]:
        """The fixed reply for a message outside the chat's domain: no answer call, nothing saved."""

        log.info("chat refused: %s by %s (p_in_scope=%s) %s: %.120s", verdict.verdict, verdict.method,
                 verdict.p_in_scope, course.get("uni_code"), question)
        return {"answer": guard_prompts.refusal(course), "status": "out_of_scope", "sources": [],
                "career_research": False, "website_research": False, "start_career_research": False,
                "notes": notes, "model": self.model, "search_question": search_question}

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return call_structured(payload, key, 90, "CampusYamu-CourseChat/0.1")

    def ask(self, question: str, course: dict[str, Any], student: dict[str, Any] | None = None,
            history: list[dict[str, str]] | None = None, user_id: str | None = None) -> dict[str, Any]:
        """Answer one question. With a user_id (and memory configured) the earlier turns come from memory
        and `history` is ignored; the turn is saved afterwards."""

        question = " ".join(str(question or "").split())[:MAX_QUESTION]
        if not question:
            raise ValueError("empty question")
        if self.guard is not None and self.guard.pattern(question):         # obvious manipulation: no calls
            return self._refusal(question, course, Verdict("manipulation", "pattern", 0.0), [], question)
        recall, search_question, notes = None, question, []
        uni_code = str(course.get("uni_code") or "")
        if user_id and self.memory is not None and uni_code:
            try:
                recall = self.memory.recall(user_id, uni_code)
                history = recall.turns
            except Exception as exc:                    # answer without memory rather than fail
                recall = None
                notes.append(f"chat memory unavailable ({str(exc)[:120]})")
        scope = None
        if self.guard is not None and self.guard.active:  # in parallel with the rewrite and the search
            self._pool = self._pool or ThreadPoolExecutor(2, thread_name_prefix="campusyamu-guard")
            scope = self._pool.submit(self.guard.check, question, course, list(history or []))
        if recall is not None:
            search_question = self.memory.standalone_question(question, recall, course)
        sources, source_notes = self.sources(course, search_question)
        notes += source_notes
        verdict = scope.result() if scope is not None else None
        if verdict is not None and verdict.blocked:
            return self._refusal(question, course, verdict, [], search_question)
        raw = self._call(self.request_payload(question, course, student or {}, history or [], sources,
                                              memory=recall.context() if recall else None,
                                              trim_history=recall is None))
        known = {s["id"] for s in sources}
        used = [s for s in raw.get("sources_used", []) if s in known]
        result = {
            "answer": str(raw.get("answer", "")).strip() or "Sorry, I could not answer that.",
            "status": raw.get("status") if raw.get("status") in STATUSES else "answered",
            "sources": [{k: s[k] for k in ("id", "kind", "title", "citation", "links") if k in s}
                        for s in sources if s["id"] in used],
            "career_research": any(s["kind"] == "career_outlook" for s in sources),
            "website_research": any(s["kind"] == "university_website" for s in sources),
            # research runs only when the student asks, and only while something is still missing
            "start_career_research": bool(raw.get("start_career_research")) and raw.get("status") != "out_of_scope"
            and not (
                any(s["kind"] == "career_outlook" for s in sources)
                and (any(s["kind"] == "university_website" for s in sources)
                     or not (self.websites is not None and self.websites.enabled))),
            "notes": notes, "model": self.model,
            "search_question": search_question,
        }
        if result["status"] == "out_of_scope":            # the prompt's own scope rule refused it
            log.info("chat refused by the model (%s): %.120s", course.get("uni_code"), question)
        elif recall is not None:
            try:
                self.memory.save_turn(user_id, course, question, result["answer"], result["sources"])
            except Exception as exc:
                notes.append(f"this turn was not saved to memory ({str(exc)[:120]})")
        return result
