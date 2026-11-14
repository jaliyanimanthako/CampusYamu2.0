"""Gap-filling research agent, run between evidence collection and the SWOT.

The fixed searches give a reliable baseline but cannot notice what they
missed (e.g. carbon assessment for quantity surveying). This agent reviews
what was collected and searches for what is missing, using the harness:

- Tool registry: one tool, ``web_search`` (the configured Tavily/Firecrawl crawler).
- Model: a cheap tool-calling model (``models.career_agent`` in settings.yaml, gpt-4o-mini).
- Context management: the transcript is compacted every 3 iterations.
- Guardrails: searches are budgeted and de-duplicated; the final answer is
  refused until the evidence is satisfactory, and every niche area it reports
  must be named in the pages it cites. Gaps that stay unfilled after the
  allowed retries are reported, never papered over.
- Agent loop: model turn, guarded tool calls, compaction, guarded finish.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .career_discovery import grounded_titles
from .firecrawl import WebSearchCrawler
from .harness import (
    AgentLoop,
    ContextManager,
    OpenAIToolModel,
    Tool,
    ToolCall,
    ToolCallingModel,
    ToolRegistry,
)
from .models import SearchQuery, WebDocument
from .source_registry import is_excluded
from .web_results import document_dict
from campusyamu.prompts.career import RESEARCH_AGENT as AGENT_PROMPT


ProgressCallback = Callable[[dict[str, Any]], None]

REQUIRED_CATEGORIES = {
    "local_live_jobs": "current local vacancies",
    "local_market": "the local labour market",
    "local_challenges": "local risks such as layoffs or oversupply",
    "global_outlook": "the worldwide outlook",
    "international_pathways": "working abroad",
    "further_study": "postgraduate study and specialisation",
    "emerging_specialisations": "niche, growing specialisations",
}
SEARCH_CATEGORIES = (*REQUIRED_CATEGORIES, "official_sources")
MIN_TRUSTED = 3
MIN_NICHE_AREAS = 3
RETRIES_PER_GAP = 2
NICHE_RETRIES = 3
# Professions usually change through these three drivers. The agent must
# search each one before it may finish (while budget remains); otherwise a
# cheap model tends to search only technology.
CHANGE_DRIVERS = {
    "technology": (
        "digital", "bim", "software", "technolog", "automat", "artificial intelligence",
        " ai ", "data", "analytics", "machine learning", "tool", "model", "tele",
        "cad", "cloud", "robot",
    ),
    "sustainability or climate": (
        "sustainab", "carbon", "climate", "green", "net zero", "energy", "environment",
        "esg", "breeam", "leed", "emission", "circular", "renewable",
    ),
    "law, regulation or contracts": (
        "law", "legal", "regulat", "compliance", "contract", "dispute", "claim",
        "arbitrat", "adjudicat", "procurement", "licens", "standard", "ethic",
        "policy", "act ", "fidic", "nec4",
    ),
}

# Words that describe a direction, not an area a student can train in.
# "Sustainable construction practices" or "AI and technology in quantity
# surveying" use only these (plus the course's own name) and are rejected.
VAGUE_WORDS = frozenset(
    {
        "sustainable", "sustainability", "green", "eco", "environmental",
        "technology", "technologies", "technological", "tech", "digital",
        "digitalisation", "digitalization", "digitisation", "ai", "artificial",
        "intelligence", "innovation", "innovative", "automation", "data",
        "tools", "software", "smart", "modern", "new", "emerging", "future",
        "trends", "trend", "practices", "practice", "skills", "skill",
        "management", "construction", "industry", "sector", "field",
        "profession", "professional", "services", "solutions", "approaches",
        "methods", "specialisation", "specialization", "specialisations",
        "specializations", "areas", "area", "and", "the", "for", "with", "in",
        "of", "to", "on", "role", "roles",
    }
)


@dataclass
class Source:
    id: str
    url: str
    title: str
    domain: str
    trusted: bool
    category: str
    text: str
    document: WebDocument | None = None  # set for sources the agent found


class ResearchState:
    """Everything the agent has: seed sources, its own finds, its searches."""

    def __init__(self, course: dict[str, Any]) -> None:
        self.course = course["course"]
        self.sources: list[Source] = []
        self._urls: set[str] = set()
        self.searches: list[dict[str, Any]] = []
        self._seen_queries = {_normal(q["query"]) for q in course.get("queries", [])}
        for document in course.get("documents", []):
            self._add(
                str(document.get("url") or ""),
                str(document.get("title") or ""),
                str(document.get("domain") or ""),
                bool(document.get("trusted")),
                str(document.get("query_category") or ""),
                " ".join(
                    str(document.get(key) or "")
                    for key in ("title", "description", "markdown")
                ),
            )

    def _add(self, url, title, domain, trusted, category, text, document=None) -> Source | None:
        key = url.rstrip("/").casefold()
        if not key or key in self._urls or is_excluded(domain):
            return None
        self._urls.add(key)
        source = Source(
            f"S{len(self.sources) + 1:03d}", url, title, domain, trusted, category, text, document
        )
        self.sources.append(source)
        return source

    def add_search(
        self,
        category: str,
        query: str,
        found: list[WebDocument],
        error: str | None = None,
    ) -> list[Source]:
        self._seen_queries.add(_normal(query))
        new = [
            source
            for document in found
            if (
                source := self._add(
                    document.url,
                    document.title,
                    document.domain,
                    document.trusted,
                    document.query_category,
                    f"{document.title} {document.description} {document.markdown}",
                    document,
                )
            )
        ]
        self.searches.append(
            {"category": category, "query": query, "new_sources": len(new), "error": error}
        )
        return new

    def searched_before(self, query: str) -> bool:
        return _normal(query) in self._seen_queries

    def attempts(self, category: str) -> int:
        return sum(search["category"] == category for search in self.searches)

    def coverage(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for source in self.sources:
            counts[source.category] = counts.get(source.category, 0) + 1
        return counts

    def trusted_count(self) -> int:
        return sum(source.trusted for source in self.sources)

    def by_id(self) -> dict[str, Source]:
        return {source.id: source for source in self.sources}

    def agent_documents(self) -> list[WebDocument]:
        return [source.document for source in self.sources if source.document is not None]


class ResearchGuardrails:
    def __init__(self, state: ResearchState, max_searches: int) -> None:
        self.state = state
        self.max_searches = max_searches
        self.niche_areas: list[dict[str, Any]] = []
        self.reported_gaps: list[str] = []

    # -- before a tool runs ------------------------------------------------
    def check_call(self, call: ToolCall) -> str | None:
        if call.name != "web_search":
            return f"Unknown tool {call.name!r}; the only tool is web_search."
        if len(self.state.searches) >= self.max_searches:
            return "Search budget used up. Write your final answer now."
        try:
            args = json.loads(call.arguments or "{}")
        except json.JSONDecodeError:
            return None  # The registry reports malformed arguments.
        query = str(args.get("query") or "").strip()
        if not 8 <= len(query) <= 300:
            return "A query must be 8 to 300 characters."
        if self.state.searched_before(query):
            return "This search was already run. Change the wording or the angle."
        return None

    # -- before the answer is accepted -------------------------------------
    def check_finish(self, answer: str) -> list[str]:
        problems: list[str] = []
        niche_lines, gap_lines = _parse_answer(answer)
        if niche_lines is None:
            problems.append(
                "Use the required format, with a 'NICHE AREAS:' section and a 'GAPS:' section."
            )
            niche_lines = []
        sources = self.state.by_id()
        course_words = set(re.findall(r"[a-z]+", self.state.course.casefold()))
        accepted = []
        for area, why, refs in niche_lines:
            words = set(re.findall(r"[a-z0-9]+", area.casefold()))
            if not words - VAGUE_WORDS - course_words:
                problems.append(
                    f"'{area}' is too broad. Name the specific method, standard, law, "
                    "contract form, certification or tool."
                )
                continue
            if not refs:
                problems.append(f"'{area}' cites no source IDs.")
                continue
            unknown = sorted(set(refs) - set(sources))
            if unknown:
                problems.append(f"'{area}' cites IDs that do not exist: {', '.join(unknown)}.")
                continue
            corpus = " ".join(sources[ref].text for ref in refs)
            if not grounded_titles([area], corpus, 1):
                problems.append(
                    f"'{area}' is not named in the pages it cites ({', '.join(refs)}). "
                    "Remove it, or search for a page that names it."
                )
                continue
            accepted.append(
                {"area": area, "why": why, "source_urls": [sources[ref].url for ref in refs]}
            )
        self.niche_areas = accepted
        self.reported_gaps = gap_lines
        problems.extend(message for message, blocking in self._gaps() if blocking)
        return problems

    def final_status(self) -> str:
        return "partial" if self._gaps() else "satisfied"

    def open_gaps(self) -> list[str]:
        return [message for message, _ in self._gaps()]

    def state_note(self) -> str:
        coverage = self.state.coverage()
        lines = [
            f"Sources held: {len(self.state.sources)} "
            f"({self.state.trusted_count()} trusted). "
            f"Searches used: {len(self.state.searches)} of {self.max_searches}.",
            "Coverage by angle: "
            + ", ".join(f"{name} {coverage.get(name, 0)}" for name in REQUIRED_CATEGORIES),
            "Sources:",
            *(
                f"  {s.id} [{s.category}{', trusted' if s.trusted else ''}] "
                f"{s.domain} | {s.title[:70]}"
                for s in self.state.sources
            ),
        ]
        if self.state.searches:
            lines.append("Your searches so far:")
            lines.extend(
                f'  "{s["query"]}" ({s["category"]}) -> {s["new_sources"]} new'
                + (f" [failed: {s['error']}]" if s["error"] else "")
                for s in self.state.searches
            )
        if self.niche_areas:
            lines.append("Niche areas already verified: " + ", ".join(a["area"] for a in self.niche_areas))
        gaps = self._gaps()
        lines.append("Open gaps:" if gaps else "Open gaps: none")
        lines.extend(
            f"  - {message}" + ("" if blocking else " (no retries left; report it under GAPS)")
            for message, blocking in gaps
        )
        return "\n".join(lines)

    def _gaps(self) -> list[tuple[str, bool]]:
        budget_left = len(self.state.searches) < self.max_searches
        coverage = self.state.coverage()
        gaps = []
        for category, label in REQUIRED_CATEGORIES.items():
            if coverage.get(category, 0) == 0:
                tries = self.state.attempts(category)
                gaps.append(
                    (
                        f"No sources about {label} (category {category}); "
                        f"tried {tries} time(s).",
                        tries < RETRIES_PER_GAP and budget_left,
                    )
                )
        trusted = self.state.trusted_count()
        if trusted < MIN_TRUSTED:
            tries = self.state.attempts("official_sources")
            gaps.append(
                (
                    f"Only {trusted} trusted official or professional-body sources; "
                    f"{MIN_TRUSTED} needed (category official_sources, name the body).",
                    tries < RETRIES_PER_GAP and budget_left,
                )
            )
        searched = " ".join(f" {s['query'].casefold()} " for s in self.state.searches)
        for driver, keywords in CHANGE_DRIVERS.items():
            if not any(keyword in searched for keyword in keywords):
                gaps.append(
                    (
                        f"You have not searched for change driven by {driver} "
                        "in this profession.",
                        budget_left,
                    )
                )
        if len(self.niche_areas) < MIN_NICHE_AREAS:
            tries = self.state.attempts("emerging_specialisations")
            gaps.append(
                (
                    f"{len(self.niche_areas)} verified niche areas; {MIN_NICHE_AREAS} needed. "
                    "Search for specific growing specialisations, then list them in your answer.",
                    tries < NICHE_RETRIES and budget_left,
                )
            )
        return gaps


def web_search_tool(
    crawler: WebSearchCrawler,
    state: ResearchState,
    region: str,
    results: int,
    emit: Callable[[dict[str, Any]], None],
) -> Tool:
    def handler(args: dict[str, Any]) -> str:
        category = str(args["category"])
        query = str(args["query"]).strip()
        stored = "field_sources" if category == "official_sources" else category
        search = SearchQuery(
            stored,
            query,
            country=region if args.get("local") else None,
            time_range="year" if args.get("recent_only") else None,
        )
        try:
            found = crawler.search_documents(search, results)
        except Exception as exc:
            state.add_search(category, query, [], str(exc))
            raise
        new = state.add_search(category, query, found)
        emit({"event": "agent_search", "category": category, "query": query, "new_sources": len(new)})
        return json.dumps(
            {
                "new_sources": [
                    {
                        "id": source.id,
                        "title": source.title,
                        "domain": source.domain,
                        "trusted": source.trusted,
                        "snippet": _snippet(source.document),
                    }
                    for source in new
                ],
                "already_held": len(found) - len(new),
            },
            ensure_ascii=False,
        )

    return Tool(
        "web_search",
        "Search the web. Returns new pages with source IDs and short snippets; "
        "pages already held are not repeated.",
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "One specific topic, e.g. a named specialisation, body, law or country.",
                },
                "category": {
                    "type": "string",
                    "enum": list(SEARCH_CATEGORIES),
                    "description": "Which research angle this search fills.",
                },
                "local": {
                    "type": "boolean",
                    "description": f"true to prefer results from {region}.",
                },
                "recent_only": {
                    "type": "boolean",
                    "description": "true to limit results to the past year.",
                },
            },
            "required": ["query", "category", "local", "recent_only"],
            "additionalProperties": False,
        },
        handler,
    )


class ResearchHarness:
    def __init__(
        self,
        crawler: WebSearchCrawler,
        model: ToolCallingModel | None = None,
        *,
        max_iterations: int = 9,
        max_searches: int = 6,
        compact_every: int = 3,
        results_per_search: int = 3,
        max_calls_per_turn: int = 3,
    ) -> None:
        self.crawler = crawler
        self.model = model
        self.max_iterations = max_iterations
        self.max_searches = max_searches
        self.compact_every = compact_every
        self.results_per_search = results_per_search
        self.max_calls_per_turn = max_calls_per_turn

    def enrich(
        self,
        web_result: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(self.aenrich(web_result, on_progress))

    async def aenrich(
        self,
        web_result: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Run one agent per course, concurrently, adding what it finds."""

        region = web_result["input"]["region"]
        content_limit = web_result["input"]["content_char_limit"]
        await asyncio.gather(
            *(
                asyncio.to_thread(self._run_course, course, region, content_limit, on_progress)
                for course in web_result["course_research"]
            )
        )
        return web_result

    def _run_course(
        self,
        course: dict[str, Any],
        region: str,
        content_limit: int,
        on_progress: ProgressCallback | None,
    ) -> None:
        name = course["course"]

        def emit(event: dict[str, Any]) -> None:
            if on_progress:
                on_progress({**event, "course": name})

        model = self.model or OpenAIToolModel()
        state = ResearchState(course)
        guardrails = ResearchGuardrails(state, self.max_searches)
        loop = AgentLoop(
            model,
            ToolRegistry((web_search_tool(self.crawler, state, region, self.results_per_search, emit),)),
            ContextManager(self.compact_every),
            guardrails,
            instructions=AGENT_PROMPT,
            max_iterations=self.max_iterations,
            max_calls_per_turn=self.max_calls_per_turn,
            on_event=emit,
        )
        emit({"event": "agent_started", "model": model.model})
        try:
            result = loop.run(_task(course, region, guardrails))
        except Exception as exc:
            course["agent_research"] = {"status": "failed", "model": model.model, "error": str(exc)}
            emit({"event": "agent_failed", "error": str(exc)})
            return

        added = state.agent_documents()
        course["documents"].extend(document_dict(document, content_limit) for document in added)
        collection = course["collection"]
        collection["agent_added"] = len(added)
        collection["retained_after_deduplication"] += len(added)
        collection["trusted_sources"] += sum(document.trusted for document in added)
        coverage = collection["category_coverage"]
        for document in added:
            coverage[document.query_category] = coverage.get(document.query_category, 0) + 1
        course["agent_research"] = {
            "status": result.status,
            "model": model.model,
            "iterations": result.iterations,
            "compactions": result.compactions,
            "searches": state.searches,
            "sources_added": len(added),
            # Accepted only after the guardrail found each area in its pages.
            "niche_areas": guardrails.niche_areas if result.answer else [],
            "unfilled_gaps": result.gaps,
            "agent_reported_gaps": guardrails.reported_gaps if result.answer else [],
            "guardrail_rejections": result.rejections,
        }


def _task(course: dict[str, Any], region: str, guardrails: ResearchGuardrails) -> str:
    discovery = course.get("career_discovery") or {}
    return "\n".join(
        [
            f"Course: {course['course']}",
            f"Student's country: {region}",
            "Career paths already searched: "
            + (", ".join(course.get("occupation_search_terms", [])) or "none"),
            "Emerging areas found by discovery: "
            + (", ".join(course.get("emerging_areas") or discovery.get("emerging_areas") or []) or "none"),
            "",
            guardrails.state_note(),
        ]
    )


NICHE_LINE = re.compile(r"^\s*[-*•]\s*(?P<area>[^:\[]+?)\s*:\s*(?P<rest>.*)$")


def _parse_answer(answer: str) -> tuple[list[tuple[str, str, list[str]]] | None, list[str]]:
    """Split the agent's answer into (area, why, refs) lines and gap lines."""

    text = answer.replace("**", "")
    match = re.search(r"NICHE AREAS\s*:(?P<niche>.*?)(?:GAPS\s*:(?P<gaps>.*))?$", text, re.S | re.I)
    if not match:
        return None, []
    niche = []
    for line in match.group("niche").splitlines():
        parsed = NICHE_LINE.match(line)
        if not parsed:
            continue
        rest = parsed.group("rest")
        refs = re.findall(r"S\d{3}", rest)
        why = re.sub(r"\[[^\]]*\]", "", rest).strip()
        niche.append((parsed.group("area").strip(), why, refs))
    gaps = [
        line.strip().lstrip("-*• ").strip()
        for line in (match.group("gaps") or "").splitlines()
        if line.strip().lstrip("-*• ").strip()
    ]
    return niche, gaps


def _snippet(document: WebDocument | None, limit: int = 500) -> str:
    if document is None:
        return ""
    text = document.description or document.markdown
    return " ".join(text.split())[:limit]


def _normal(query: str) -> str:
    return " ".join(query.casefold().split())
