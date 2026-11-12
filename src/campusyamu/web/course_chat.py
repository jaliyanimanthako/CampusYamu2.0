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

One OpenAI Responses call per question (strict JSON). The model may only cite
the sources given; unknown ids are dropped. Nothing is stored server side:
the browser sends the conversation history with each question.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from campusyamu.core import settings

from campusyamu.agents.course_details import HandbookCourseIndex
from campusyamu.core.openai_client import call_structured

from .career_outlook import CareerOutlookStore

DEFAULT_MODEL = "gpt-4o-mini"
MAX_QUESTION = 1000
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

SYSTEM_PROMPT = """You answer a Sri Lankan A/L student's questions about ONE state-university course they can
apply for, using only the numbered sources given:
- S1, S2 ...: the course's own section of the UGC 2024/2025 handbook.
- R: the student's own computed facts for this course (Z-score band, last cut-off, margin, travel time,
  O/L status, ranking position). Bands describe last year's cut-offs only: strong = at or above,
  competitive = close, reach = a little below, unlikely = well below. They are not admission chances.
- H1, H2 ...: other handbook passages found by search (may be about general rules or other courses).
- C (only if present): web research on careers for this course in Sri Lanka (career paths, a 5-year SWOT,
  local vs overseas work, further study), dated, with evidence ids (E001 ...) whose titles and URLs are listed.
  Use it for jobs, demand, salaries, further study and future outlook. Say it comes from web research on that
  date and may change; mention the evidence title or site when useful.
- If C is absent and the student asks about careers, say there is no career research for this course yet and
  offer it: "I can look this up on the web (takes about 2-3 minutes) - just ask me to research it."
- start_career_research: true ONLY when the student explicitly asks you to research / search / look up careers
  or jobs for this course on the web, or clearly accepts your offer to do so (e.g. "yes, research it"). Otherwise
  false. Always false when C is present. When true, tell them the research has started and they can keep asking.
Rules:
- Answer in simple English, briefly (2-6 sentences or a short list). Cite sources inline like [S1] or [R].
- Use only the sources. If they do not answer the question, say the handbook does not say, and suggest
  contacting the university or UGC. Do not guess dates, fees, rankings or career facts.
- Never promise admission. Do not invent numbers.
- If an H passage is about a different course, do not apply it to this course."""


def _trim(value: Any, limit: int = 600) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return value if len(text) <= limit else text[:limit] + "…"


class CourseChat:
    def __init__(self, handbook: HandbookCourseIndex | None = None, model: str | None = None,
                 use_search: bool = True, outlooks: CareerOutlookStore | None = None) -> None:
        self.handbook = handbook or HandbookCourseIndex()
        self.outlooks = outlooks or CareerOutlookStore()
        self.model = model or settings.model("chat", "CHAT_MODEL", DEFAULT_MODEL)
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

    # --- one question ------------------------------------------------------------------
    def sources(self, course: dict[str, Any], question: str) -> tuple[list[dict[str, Any]], list[str]]:
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
                        history: list[dict[str, str]], sources: list[dict[str, Any]]) -> dict[str, Any]:
        turns = []
        for turn in history[-MAX_HISTORY_TURNS:]:
            if turn.get("role") in ("user", "assistant") and str(turn.get("content", "")).strip():
                turns.append({"role": turn["role"], "content": str(turn["content"])[:MAX_HISTORY_CHARS]})
        context = {
            "course": f"{course.get('course_name')} ({course.get('uni_code')}) — {course.get('university')}",
            "student": {k: _trim(v) for k, v in student.items()},
            "sources": [{k: s[k] for k in ("id", "title", "citation", "text")} for s in sources],
        }
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["answer", "sources_used", "status", "start_career_research"],
            "properties": {
                "start_career_research": {"type": "boolean"},
                "answer": {"type": "string"},
                "sources_used": {"type": "array", "items": {"type": "string", "enum": [s["id"] for s in sources]}},
                "status": {"type": "string", "enum": ["answered", "partly_answered", "not_in_sources"]},
            },
        }
        return {
            "model": self.model, "store": False, "max_output_tokens": 1500,
            "input": [{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "system", "content": "Context:\n" + json.dumps(context, ensure_ascii=False, default=str)},
                      *turns, {"role": "user", "content": question}],
            "text": {"format": {"type": "json_schema", "name": "course_answer", "strict": True, "schema": schema}},
        }

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return call_structured(payload, key, 90, "CampusYamu-CourseChat/0.1")

    def ask(self, question: str, course: dict[str, Any], student: dict[str, Any] | None = None,
            history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        question = " ".join(str(question or "").split())[:MAX_QUESTION]
        if not question:
            raise ValueError("empty question")
        sources, notes = self.sources(course, question)
        raw = self._call(self.request_payload(question, course, student or {}, history or [], sources))
        known = {s["id"] for s in sources}
        used = [s for s in raw.get("sources_used", []) if s in known]
        return {
            "answer": str(raw.get("answer", "")).strip() or "Sorry, I could not answer that.",
            "status": raw.get("status") if raw.get("status") in ("answered", "partly_answered", "not_in_sources")
            else "answered",
            "sources": [{k: s[k] for k in ("id", "kind", "title", "citation", "links") if k in s}
                        for s in sources if s["id"] in used],
            "career_research": any(s["kind"] == "career_outlook" for s in sources),
            "start_career_research": bool(raw.get("start_career_research"))
            and not any(s["kind"] == "career_outlook" for s in sources),
            "notes": notes, "model": self.model,
        }
