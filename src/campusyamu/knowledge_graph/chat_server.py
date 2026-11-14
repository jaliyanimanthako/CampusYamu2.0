"""Local chat assistant over the admissions knowledge graph.

    uv run python -m campusyamu.knowledge_graph.chat_server
    # then open http://127.0.0.1:8765

Serves the graph browser page and ``POST /api/chat``. The OpenAI key stays on
the server (read from the environment / .env like the extraction pipeline);
the browser never sees it. The model (default gpt-4o-mini) answers only
through graph tools -- search, node details, eligibility checks, offerings --
so every course, rule and number in an answer comes from the graph, with
handbook citations. Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import networkx as nx

from .build_graph import DEFAULT_OUTPUT, load_graph
from .eligibility import EligibilityChecker, make_student
from .graph_viewer import render_viewer
from .handbook_prose import PROJECT_ROOT, _load_env
from campusyamu.prompts.kg_chat import KG_CHAT_SYSTEM as SYSTEM_PROMPT

DEFAULT_MODEL = "gpt-4o-mini"
MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 12
MAX_MESSAGE_CHARS = 2000
MAX_BODY_BYTES = 64_000
SEARCH_TYPES = {"Course", "Institution", "Subject", "DegreeProgramme", "Stream", "Offering", "CourseGroup"}


def _tool(name: str, description: str, properties: dict[str, Any], required: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required),
                           "additionalProperties": False},
        },
    }


TOOL_SPECS = [
    _tool("search_nodes", "Find graph nodes (courses, universities, subjects, degree programmes, streams, "
          "UGC codes) by name. Returns ids to use with other tools.",
          {"query": {"type": "string"},
           "types": {"type": "array", "items": {"type": "string", "enum": sorted(SEARCH_TYPES)}}},
          ["query"]),
    _tool("get_node", "Details of one node: properties, rule summary, handbook text and citation, and "
          "its connections (e.g. a course's requirements, a subject's courses).",
          {"node_id": {"type": "string"}}, ["node_id"]),
    _tool("check_eligibility", "Check course eligibility for a student's three A/L subjects. Without "
          "'course' it lists eligible courses; with 'course' (id or name) it explains that course.",
          {"subjects": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
              "type": "object", "properties": {"subject": {"type": "string"},
                                               "grade": {"type": "string", "enum": ["A", "B", "C", "S", "F"]}},
              "required": ["subject", "grade"], "additionalProperties": False}},
           "stream": {"type": "string"}, "cgp": {"type": "integer"}, "course": {"type": "string"}},
          ["subjects"]),
    _tool("course_offerings", "Universities offering ONE COURSE, with UGC codes, proposed intakes, O/L "
          "requirements, aptitude tests and degree programmes. Not for universities.",
          {"course": {"type": "string", "description": "Course id (course:008) or course name"}}, ["course"]),
    _tool("institution_offerings", "All courses offered by ONE UNIVERSITY (including its campuses and "
          "institutes): UGC codes, intakes, O/L requirements, aptitude tests, listed degree programmes.",
          {"institution": {"type": "string", "description": "Institution id or university name"}},
          ["institution"]),
]
STOPWORDS = {"of", "the", "and", "in", "for", "at", "a", "an", "to", "on", "with", "&"}


class GraphTools:
    """Deterministic, read-only tools the model may call."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self.checker = EligibilityChecker(graph)
        self.index = [
            (node, attrs) for node, attrs in graph.nodes(data=True) if attrs["type"] in SEARCH_TYPES
        ]
        self.touched: list[str] = []

    def _label(self, node: str) -> str:
        attrs = self.graph.nodes[node]
        if attrs["type"] == "Offering":
            course = next((t for _, t, k in self.graph.out_edges(node, keys=True) if k == "OFFERS_COURSE"), None)
            place = next((t for _, t, k in self.graph.out_edges(node, keys=True) if k == "AT_INSTITUTION"), None)
            return (f"{attrs.get('uni_code')} {self.graph.nodes[course]['name'] if course else ''}"
                    f" @ {self.graph.nodes[place]['name'] if place else ''}").strip()
        return str(attrs.get("name") or attrs.get("uni_code") or attrs.get("section_number") or node)

    @staticmethod
    def _words(text: str) -> list[str]:
        return [w for w in re.findall(r"[a-z0-9]+", text.casefold()) if w not in STOPWORDS]

    def search_nodes(self, query: str, types: Sequence[str] | None = None) -> dict[str, Any]:
        """Whole-word matching (a query word matches a label word or its prefix, 3+ letters)."""

        words = self._words(query)
        scored = []
        for node, attrs in self.index:
            if types and attrs["type"] not in types or not words:
                continue
            label = self._label(node)
            label_words = self._words(label)
            matched = sum(
                any(lw == w or (len(w) >= 3 and lw.startswith(w)) for lw in label_words) for w in words
            )
            if not matched:
                continue
            score = matched / len(words) + (1.0 if label.casefold() == query.casefold().strip() else 0)
            scored.append((score, node, attrs["type"], label))
        scored.sort(key=lambda item: (-item[0], len(item[3])))
        results = [{"id": n, "type": t, "label": l, "match": round(sc, 2)} for sc, n, t, l in scored[:10]]
        self.touched += [r["id"] for r in results[:3] if r["match"] >= 1]
        return {"results": results}

    def _resolve(self, value: str, kind: str) -> tuple[str | None, dict[str, Any] | None]:
        """Exact id, or a confident whole-word name match of ``kind``; otherwise an error."""

        if value in self.graph and self.graph.nodes[value]["type"] == kind:
            return value, None
        hits = [h for h in self.search_nodes(value)["results"] if h["match"] >= 1]
        same_kind = [h for h in hits if h["type"] == kind]
        if same_kind:
            return same_kind[0]["id"], None
        other = hits[0] if hits else None
        hint = (f" {value!r} is a {other['type']} ({other['label']}, id {other['id']})." if other else "")
        tool = {"Institution": "institution_offerings", "Course": "course_offerings"}.get(
            other["type"] if other else "", "search_nodes or get_node")
        return None, {"error": f"No {kind} matching {value!r}.{hint} Use {tool} instead."
                      if other else f"No {kind} matching {value!r}. Use search_nodes to find the right name."}

    def get_node(self, node_id: str) -> dict[str, Any]:
        if node_id not in self.graph:
            return {"error": f"No node {node_id!r}; use search_nodes first."}
        from .graph_viewer import _details

        attrs = self.graph.nodes[node_id]
        self.touched.append(node_id)
        citations, connections, counts = [], [], {}
        for _, target, key, edge in self.graph.out_edges(node_id, keys=True, data=True):
            if key == "CITED_FROM":
                citations.append({"section": self.graph.nodes[target].get("section_number"),
                                  "pdf_page": edge.get("pdf_page"),
                                  "line": edge.get("markdown_line_start")})
                continue
            counts[key] = counts.get(key, 0) + 1
            connections.append({"relationship": key, "direction": "out", "id": target,
                                "type": self.graph.nodes[target]["type"], "label": self._label(target)})
        for source, _, key in self.graph.in_edges(node_id, keys=True):
            counts[f"<-{key}"] = counts.get(f"<-{key}", 0) + 1
            connections.append({"relationship": key, "direction": "in", "id": source,
                                "type": self.graph.nodes[source]["type"], "label": self._label(source)})
        return {"id": node_id, "type": attrs["type"], "label": self._label(node_id),
                "details": _details(node_id, attrs), "citations": citations,
                "relationship_counts": counts, "connections": connections[:40],
                "more_connections": max(0, len(connections) - 40)}

    def check_eligibility(self, subjects: Sequence[dict[str, str]], stream: str | None = None,
                          cgp: int | None = None, course: str | None = None) -> dict[str, Any]:
        try:
            student = make_student([f"{s['subject']}:{s['grade']}" for s in subjects], stream,
                                   30 if cgp is None else cgp)
        except (ValueError, KeyError) as exc:
            return {"error": str(exc)}
        summary = {"subjects": [f"{s} ({g})" for s, g in student.grades], "stream": student.stream,
                   "cgp": student.cgp,
                   "note": "Eligibility = handbook minimum subject requirements. Selection also needs "
                           "the Z-score cut-off, which is not in this data."}
        if course:
            course_id, error = self._resolve(course, "Course")
            if error:
                return error
            result = asdict(self.checker.check_course(course_id, student))
            self.touched.append(course_id)
            result["programme_requirements"] = [p for p in result["programme_requirements"] if not p["met"]]
            return {**summary, "course": result}
        results = self.checker.check_all(student)
        eligible = [r for r in results if r.decision == "eligible"]
        self.touched += [r.course_id for r in eligible]

        def brief(r):
            flags = []
            if any(o["ol_requirements"] for o in r.offerings):
                flags.append("O/L requirements at some universities")
            if any(o["aptitude_test"] for o in r.offerings):
                flags.append("aptitude test")
            if r.additional_conditions:
                flags.append("additional conditions")
            closed = [p["programme"] for p in r.programme_requirements if not p["met"]]
            if closed:
                flags.append(f"{len(closed)} programme(s) not open")
            return {"id": r.course_id, "name": r.name, "flags": flags}

        return {**summary, "eligible": [brief(r) for r in eligible],
                "check_handbook": [{"id": r.course_id, "name": r.name, "text": r.unresolved_text}
                                   for r in results if r.decision == "check_handbook"],
                "not_eligible_count": sum(r.decision == "not_eligible" for r in results)}

    def course_offerings(self, course: str) -> dict[str, Any]:
        course_id, error = self._resolve(course, "Course")
        if error:
            return error
        self.touched.append(course_id)
        node = self.graph.nodes[course_id]
        programmes = sorted({
            (self.graph.nodes[p]["name"], self.graph.nodes[p]["university"])
            for p, _, k in self.graph.in_edges(course_id, keys=True) if k == "UNDER_COURSE"
        })
        return {"course": {"id": course_id, "name": node["name"], "code": node.get("code"),
                           "total_proposed_intake": node.get("total_proposed_intake")},
                "offerings": self.checker.offerings(course_id),
                "degree_programmes": [{"name": n, "university": u} for n, u in programmes][:60]}

    def institution_offerings(self, institution: str) -> dict[str, Any]:
        """Every course a university offers (with its campuses and institutes)."""

        institution_id, error = self._resolve(institution, "Institution")
        if error:
            return error
        places = [institution_id] + [
            s for s, _, k in self.graph.in_edges(institution_id, keys=True) if k == "PART_OF"
        ]
        self.touched.append(institution_id)
        courses = []
        for place in places:
            for offering, _, key in self.graph.in_edges(place, keys=True):
                if key != "AT_INSTITUTION" or self.graph.nodes[offering]["type"] != "Offering":
                    continue
                course_id = next(t for _, t, k in self.graph.out_edges(offering, keys=True) if k == "OFFERS_COURSE")
                entry = next(o for o in self.checker.offerings(course_id)
                             if o["uni_code"] == self.graph.nodes[offering].get("uni_code"))
                courses.append({"course_id": course_id, "course": self.graph.nodes[course_id]["name"], **entry})
                self.touched.append(course_id)
        programmes = sorted(
            self.graph.nodes[s]["name"] for place in places
            for s, _, k in self.graph.in_edges(place, keys=True)
            if k == "AT_INSTITUTION" and self.graph.nodes[s]["type"] == "DegreeProgramme"
        )
        return {"institution": {"id": institution_id, "name": self.graph.nodes[institution_id]["name"],
                                "campuses_included": [self.graph.nodes[p]["name"] for p in places[1:]]},
                "course_count": len(courses),
                "courses": sorted(courses, key=lambda c: c["uni_code"] or ""),
                "listed_degree_programmes": programmes}

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler: Callable[..., dict[str, Any]] | None = {
            "search_nodes": self.search_nodes, "get_node": self.get_node,
            "check_eligibility": self.check_eligibility, "course_offerings": self.course_offerings,
            "institution_offerings": self.institution_offerings,
        }.get(name)
        if handler is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return handler(**arguments)
        except TypeError as exc:
            return {"error": f"Bad arguments for {name}: {exc}"}


class ChatModel(Protocol):
    model: str

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]: ...


class OpenAIChatClient:
    """Minimal Chat Completions client with tool calling (stdlib only)."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None, timeout: int = 60) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY (environment or .env) to use the chat")
        self.timeout = timeout

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto",
                   "temperature": 0.2}
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": "CampusYamu-GraphChat/0.1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc
        return body["choices"][0]["message"]


class ChatAgent:
    def __init__(self, graph: nx.MultiDiGraph, model: ChatModel) -> None:
        self.graph = graph
        self.model = model

    def answer(self, history: Sequence[dict[str, str]]) -> dict[str, Any]:
        cleaned = [
            {"role": m["role"], "content": str(m["content"])[:MAX_MESSAGE_CHARS]}
            for m in history[-MAX_HISTORY:]
            if m.get("role") in {"user", "assistant"} and str(m.get("content", "")).strip()
        ]
        if not cleaned or cleaned[-1]["role"] != "user":
            return {"reply": "Please ask a question.", "highlight": [], "tools": []}
        tools = GraphTools(self.graph)
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *cleaned]
        used: list[str] = []
        for _ in range(MAX_TOOL_ROUNDS):
            message = self.model.complete(messages, TOOL_SPECS)
            calls = message.get("tool_calls") or []
            if not calls:
                highlight = list(dict.fromkeys(n for n in tools.touched if n in self.graph))[:150]
                return {"reply": message.get("content") or "", "highlight": highlight, "tools": used}
            messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = tools.call(name, arguments) if isinstance(arguments, dict) else {"error": "bad arguments"}
                used.append(name)
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(result, ensure_ascii=False)[:24_000]})
        return {"reply": "Sorry, I could not finish that answer. Please ask in a simpler way.",
                "highlight": [], "tools": used}


def make_handler(page: str, agent_factory: Callable[[], ChatAgent | None], model_name: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, value: dict[str, Any]) -> None:
            self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json")

        def do_GET(self) -> None:  # noqa: N802
            if self.path in {"/", "/index.html"}:
                self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self._json(200, {"ok": True, "model": model_name, "llm": agent_factory() is not None})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/chat":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._json(413, {"error": "request too large"})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                history = body["messages"]
                if not isinstance(history, list):
                    raise ValueError
            except (ValueError, KeyError, UnicodeDecodeError):
                self._json(400, {"error": "expected {\"messages\": [...]}"})
                return
            agent = agent_factory()
            if agent is None:
                self._json(503, {"error": "OPENAI_API_KEY is not set on the server"})
                return
            try:
                self._json(200, agent.answer(history))
            except RuntimeError as exc:
                self._json(502, {"error": str(exc)})

        def log_message(self, fmt: str, *args: Any) -> None:  # keep the console quiet
            if "/api/chat" in (args[0] if args else ""):
                super().log_message(fmt, *args)

    return Handler


def bind_server(handler, first_port: int, attempts: int = 20) -> ThreadingHTTPServer | None:
    """Bind 127.0.0.1 on the first free port from ``first_port`` (another app may hold it)."""

    for port in range(first_port, first_port + attempts):
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as exc:
            if exc.errno not in {errno.EADDRINUSE, errno.EACCES}:
                raise
            print(f"Port {port} is in use, trying {port + 1}...")
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the graph browser with a chat assistant.")
    parser.add_argument("--graph", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--model", default=os.getenv("CHAT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    _load_env(args.env_file)
    graph = load_graph(args.graph)
    page = render_viewer(graph, chat=True)
    client: list[OpenAIChatClient | None] = [None]
    try:
        client[0] = OpenAIChatClient(args.model)
    except RuntimeError as exc:
        print(f"Chat disabled: {exc}")

    def factory() -> ChatAgent | None:
        return ChatAgent(graph, client[0]) if client[0] else None

    server = bind_server(make_handler(page, factory, args.model), args.port)
    if server is None:
        print(f"No free port between {args.port} and {args.port + 19}; pass --port.")
        return 1
    port = server.server_address[1]
    print(f"Graph browser with chat ({args.model}) at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
