"""Small local web front end for the student pipeline.

    uv run python -m web_app              # http://127.0.0.1:8770
    uv run python -m web_app --port 8771

GET  /              the form + results page (web_app/static/index.html)
GET  /api/options   dropdown values: streams, subjects, grades, districts, DS divisions by district
POST /api/run       run the LangGraph pipeline for one student; returns the report JSON
POST /api/ask       "Ask about this course": one question about one course (course_chat.py)
GET  /api/career?course=NAME   cached career outlook (web agent) + research job status
POST /api/career/research      start the web agent for one course (background, minutes)

Requests are handled one at a time (the pipeline holds SQLite connections).
OpenAI is used only if OPENAI_API_KEY is set (.env) and the form asks for it.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from course_finder.finder import AL_GRADES, OL_GRADES, CourseFinder
from RAG_Agent.graph_pipeline.al_clause_parsers import canonical_subject
from RAG_Agent.graph_pipeline.handbook_prose import OWNER_INTERPRETATIONS, _load_env
from student_pipeline.graph import build_pipeline, run_pipeline

from .career_outlook import CareerOutlookStore, CareerResearchJobs, missing_keys
from .course_chat import CourseChat

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8770
MAX_BODY = 64_000
OL_FORM_SUBJECTS = ["Science", "English", "Mathematics"]
# Form help only (defaults when the stream changes, and a soft warning when the
# subjects don't fit the stream). Eligibility never uses these: it is decided by
# the subjects themselves. Biological / Physical Science use the owner's
# stream_subjects lists (owner_interpretations.json); the rest are common practice.
STREAM_FORM_HINTS = {
    "Commerce": {"defaults": ["Accounting", "Business Studies", "Economics"],
                 "required_any": ["Accounting", "Business Studies", "Economics"]},
    "Engineering Technology": {"defaults": ["Engineering Technology", "Science for Technology",
                                            "Information & Communication Technology"],
                               "required_all": ["Engineering Technology", "Science for Technology"]},
    "Biosystems Technology": {"defaults": ["Biosystems Technology", "Science for Technology", "Agricultural Science"],
                              "required_all": ["Biosystems Technology", "Science for Technology"]},
    "Arts": {"defaults": []},
    "Information Communication Technology": {"defaults": []},
}
OWNER_STREAM_DEFAULTS = {"Biological Science": ["Biology", "Chemistry", "Physics"],
                         "Physical Science": ["Combined Mathematics", "Physics", "Chemistry"]}


class WebApp:
    def __init__(self) -> None:
        self.finder = CourseFinder()
        self.outlooks = CareerOutlookStore()
        self.career_jobs = CareerResearchJobs(self.outlooks)
        self.chat = CourseChat(outlooks=self.outlooks)
        self._pipelines: dict[tuple[bool, int], Any] = {}
        self.options = self._options()
        self.course_names = {a["name"] for _, a in self.finder.graph.nodes(data=True) if a["type"] == "Course"}

    def pipeline(self, use_llm: bool, suggestions: int = 20):
        key = (use_llm, suggestions)
        if key not in self._pipelines:
            self._pipelines[key] = build_pipeline(self.finder, use_llm=use_llm, suggestions=suggestions)
        return self._pipelines[key]

    def _options(self) -> dict[str, Any]:
        graph = self.finder.graph
        streams = [a["name"] for _, a in graph.nodes(data=True) if a["type"] == "Stream"]
        subjects = sorted({s for _, a in graph.nodes(data=True) if a["type"] == "Subject"
                           and (s := canonical_subject(a["name"]))})
        ds_by_district: dict[str, list[str]] = {}
        for origin in self.finder.travel.ds_divisions():
            ds_by_district.setdefault(origin.district, []).append(origin.ds_division)
        return {
            "streams": streams,
            "stream_hints": self._stream_hints(streams),
            "al_subjects": subjects,
            "al_grades": list(AL_GRADES),
            "ol_subjects": OL_FORM_SUBJECTS,
            "ol_grades": list(OL_GRADES),
            "districts": sorted(ds_by_district),
            "ds_divisions": {d: sorted(v) for d, v in sorted(ds_by_district.items())},
            "llm_available": bool(os.getenv("OPENAI_API_KEY")),
        }

    @staticmethod
    def _stream_hints(streams: list[str]) -> dict[str, Any]:
        try:
            owner = json.loads(Path(OWNER_INTERPRETATIONS).read_text(encoding="utf-8"))
            owner_lists = owner.get("stream_subjects", {}).get("streams", {})
        except (OSError, ValueError):
            owner_lists = {}
        hints = {}
        for stream in streams:
            if stream in owner_lists:
                hints[stream] = {"defaults": OWNER_STREAM_DEFAULTS.get(stream, owner_lists[stream][:3]),
                                 "allowed": owner_lists[stream], "source": "owner stream_subjects"}
            else:
                hints[stream] = {**STREAM_FORM_HINTS.get(stream, {"defaults": []}), "source": "form hint"}
        return hints

    def career(self, course: str) -> dict[str, Any]:
        outlook = self.outlooks.get(course) if course else None
        missing = missing_keys()
        return {
            "course": course,
            "available": not missing, "missing_keys": missing,
            "outlook": None if not outlook else {
                "generated_at": outlook.get("generated_at"), "status": outlook.get("status"),
                "sources": len(outlook.get("evidence_index", [])),
                "overall": (outlook.get("analysis") or {}).get("overall_outlook"),
            },
            "job": self.career_jobs.status(course) if course else None,
        }

    def start_career(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        course = str(body.get("course") or "").strip()
        if not course or course not in self.course_names:
            return 400, {"errors": ["Unknown course"]}
        if missing := missing_keys():
            return 400, {"errors": ["Career research needs " + ", ".join(missing) + " in .env"]}
        started, message = self.career_jobs.start(course)
        return (202 if started else 409), {"message": message, **self.career(course)}

    def ask(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if not self.options["llm_available"]:
            return 400, {"errors": ["The course chat needs OPENAI_API_KEY in .env"]}
        course = body.get("course") or {}
        if not course.get("course_code") or not str(body.get("question") or "").strip():
            return 400, {"errors": ["Give a course and a question"]}
        history = [t for t in body.get("history") or [] if isinstance(t, dict)]
        try:
            result = self.chat.ask(body["question"], course, body.get("student") or {}, history)
        except (RuntimeError, ValueError) as exc:
            return 502, {"errors": [f"Could not answer: {exc}"]}
        name = str(course.get("course_name") or "")
        if result.pop("start_career_research", False) and name in self.course_names:
            # only when the student asked for it in the chat
            if missing := missing_keys():
                result["notes"].append("career research is not configured (" + ", ".join(missing) + ")")
            else:
                started, message = self.career_jobs.start(name)
                if not started:
                    result["notes"].append(message)
        result["career"] = self.career(name) if name else None
        return 200, result

    def run(self, form: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            al = [f"{r['subject']}:{r['grade']}" for r in form.get("al", []) if r.get("subject")]
            ol = [f"{r['subject']}:{r['grade']}" for r in form.get("ol", []) if r.get("grade")]
            z = form.get("z_score")
            inputs = {
                "stream": form.get("stream"),
                "al": al,
                "cgt": int(form.get("cgt") or 0),
                "admission_district": form.get("admission_district"),
                "home": form.get("ds_division"),
                "ol": ol,
                "z_score": float(z) if z not in (None, "") else None,
                "preferences": (form.get("preferences") or "").strip(),
            }
        except (TypeError, ValueError, KeyError) as exc:
            return 400, {"errors": [f"Invalid form value: {exc}"]}
        missing = [label for key, label in (("stream", "stream"), ("admission_district", "admission district"),
                                            ("home", "home DS division")) if not inputs[key]]
        if len(al) != 3:
            missing.append("three A/L subjects")
        if len({a.split(':')[0] for a in al}) != len(al):
            return 400, {"errors": ["Choose three different A/L subjects"]}
        if missing:
            return 400, {"errors": ["Please fill in: " + ", ".join(missing)]}
        use_llm = bool(form.get("use_llm")) and self.options["llm_available"]
        try:
            suggestions = max(5, min(50, int(form.get("suggestions") or 20)))
        except (TypeError, ValueError):
            suggestions = 20
        state = run_pipeline(inputs, self.pipeline(use_llm, suggestions))
        if state.get("errors"):
            return 400, {"errors": state["errors"]}
        return 200, {"report": state["report"], "used_llm": use_llm}


def make_handler(web: WebApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CampusYamuWeb/0.1"

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: Any) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/options":
                self._json(200, web.options)
            elif self.path.startswith("/api/career?"):
                query = parse_qs(urlparse(self.path).query)
                self._json(200, web.career((query.get("course") or [""])[0]))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in ("/api/run", "/api/ask", "/api/career/research"):
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._json(413, {"errors": ["request too large"]})
                return
            try:
                form = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"errors": ["invalid JSON"]})
                return
            try:
                handler = {"/api/ask": web.ask, "/api/career/research": web.start_career}.get(self.path, web.run)
                status, data = handler(form)
            except Exception as exc:                      # keep the server up; show the reason
                traceback.print_exc()
                status, data = 500, {"errors": [f"Request failed: {exc}"]}
            self._json(status, data)

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write(f"[web] {self.address_string()} {fmt % args}\n")

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args(argv)
    try:
        _load_env(args.env_file)
    except Exception as exc:
        print(f"warning: could not load env file: {exc}", file=sys.stderr)
    web = WebApp()
    try:
        server = HTTPServer((args.host, args.port), make_handler(web))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            print(f"Port {args.port} is in use; try --port {args.port + 1}", file=sys.stderr)
            return 1
        raise
    print(f"CampusYamu web app on http://{args.host}:{args.port}  "
          f"(OpenAI {'available' if web.options['llm_available'] else 'not configured: offline mode'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        web.finder.close()
        web.chat.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
