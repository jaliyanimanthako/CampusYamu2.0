"""The CampusYamu backend logic behind the API (campusyamu.api.app).

Course finder + LangGraph pipeline, course chat and career-outlook jobs, wrapped in
one object. Holds SQLite connections, so it must be used from a single thread.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from campusyamu.agents.course_finder.finder import AL_GRADES, OL_GRADES, CourseFinder
from campusyamu.agents.preference import engine_available, preference_engine
from campusyamu.knowledge_graph.al_clause_parsers import canonical_subject
from campusyamu.knowledge_graph.handbook_prose import OWNER_INTERPRETATIONS
from campusyamu.memory import ChatMemory
from campusyamu.pipeline.graph import build_pipeline, run_pipeline

from campusyamu.web.career_outlook import CareerOutlookStore, CareerResearchJobs, missing_keys
from campusyamu.web.course_chat import CourseChat
from campusyamu.web.university_pages import UniversityPages

from .limits import DailyLimits

log = logging.getLogger(__name__)

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


def course_from_report(report: dict[str, Any], uni_code: str) -> dict[str, Any] | None:
    """The chat's course row for one offering, from a saved report: its band row plus its place in the
    distance ranking (the same fields the web page adds)."""

    row = next((r for band in (report.get("bands") or {}).values() for r in band if r.get("uni_code") == uni_code), None)
    if row is None:
        return None
    order3 = (report.get("rankings") or {}).get("distance") or {}
    pick = next((x for x in order3.get("suggestions") or [] if x.get("uni_code") == uni_code), {})
    note = (((order3.get("feedback") or {}).get("course_notes") or {}).get(uni_code) or {}).get("note")
    return {**row, "order3_position": pick.get("position"), "parts": pick.get("parts"), "order3_note": note}


def student_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """The chat's student facts from a saved report."""

    profile, origin = report.get("profile") or {}, report.get("origin") or {}
    return {"stream": profile.get("stream"), "al_results": profile.get("al_results"),
            "z_score": profile.get("z_score"), "admission_district": profile.get("admission_district"),
            "home": f"{origin.get('ds_division')} ({origin.get('district')})",
            "interests": (report.get("preferences") or {}).get("text", "")}


class AdvisorService:
    """Everything the API serves; methods return (status, body) or plain dicts. Not thread-safe:
    the API calls it from one worker thread (see app.Service)."""

    def __init__(self) -> None:
        self.finder = CourseFinder()
        self.outlooks = CareerOutlookStore()
        self.websites = UniversityPages()                 # chat.website.enabled decides if the chat uses it
        self.career_jobs = CareerResearchJobs(self.outlooks, websites=self.websites)
        self.memory = ChatMemory()                         # opens its store on first use
        self.chat = CourseChat(outlooks=self.outlooks, websites=self.websites, memory=self.memory)
        self.limits = DailyLimits(lambda: self.memory.store)
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
            "llm_available": bool(os.getenv("OPENAI_API_KEY")),      # OpenAI: chat, feedback
            "preference_engine": preference_engine(),                # AI that reads the interests
            "preference_ai_available": engine_available(),
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

    def start_career(self, body: dict[str, Any], user_id: str | None = None) -> tuple[int, dict[str, Any]]:
        course = str(body.get("course") or "").strip()
        if not course or course not in self.course_names:
            return 400, {"errors": ["Unknown course"]}
        if missing := missing_keys():
            return 400, {"errors": ["Career research needs " + ", ".join(missing) + " in .env"]}
        if over := self.limits.check(user_id, "research"):
            return 429, {"errors": [over]}
        started, message = self.career_jobs.start(course)
        if started:
            self.limits.record(user_id, "research")
        return (202 if started else 409), {"message": message, **self.career(course)}

    def ask(self, body: dict[str, Any], user_id: str | None = None) -> tuple[int, dict[str, Any]]:
        """One chat question. With user_id (a signed-in student) the server's memory replaces `history`."""

        if not self.options["llm_available"]:
            return 400, {"errors": ["The course chat needs OPENAI_API_KEY in .env"]}
        course = body.get("course") or {}
        student = body.get("student") or {}
        if not course.get("course_code") and body.get("uni_code") and user_id:
            saved = self.memory.store.results(user_id)          # the course from the student's saved search
            course = course_from_report(saved["report"], str(body["uni_code"])) if saved else None
            if course is None:
                return 400, {"errors": [f"{body['uni_code']} is not in your saved results: search again first"]}
            student = student or student_from_report(saved["report"])
        if not course.get("course_code") or not str(body.get("question") or "").strip():
            return 400, {"errors": ["Give a course (or, signed in, its uni_code) and a question"]}
        if over := self.limits.check(user_id, "chat"):
            return 429, {"errors": [over]}
        history = [t for t in body.get("history") or [] if isinstance(t, dict)]
        try:
            result = self.chat.ask(body["question"], course, student, history, user_id=user_id)
        except (RuntimeError, ValueError) as exc:
            return 502, {"errors": [f"Could not answer: {exc}"]}
        name = str(course.get("course_name") or "")
        if result.pop("start_career_research", False) and name in self.course_names:
            # only when the student asked for it in the chat
            if missing := missing_keys():
                result["notes"].append("career research is not configured (" + ", ".join(missing) + ")")
            elif over := self.limits.check(user_id, "research"):
                result["notes"].append(over)
            else:                                       # careers + the university website + specialisations
                offering = {k: course.get(k) for k in ("uni_code", "course_code", "course_name", "university")}
                started, message = self.career_jobs.start(name, offering)
                if started:
                    self.limits.record(user_id, "research")
                else:
                    result["notes"].append(message)
        result["career"] = self.career(name) if name else None
        result["usage"] = self.limits.record(user_id, "chat")
        return 200, result

    # --- the signed-in student's own data (GET/DELETE /v1/me...) ------------------------------
    def me(self, user_id: str) -> dict[str, Any]:
        return {"user_id": user_id, "usage": self.limits.status(user_id)}

    def results(self, user_id: str) -> tuple[int, dict[str, Any]]:
        """The student's latest search: the form they sent and the report."""

        saved = self.memory.store.results(user_id)
        if saved is None:
            return 404, {"errors": ["No saved results yet: run a search first"]}
        return 200, saved

    def chats(self, user_id: str) -> list[dict[str, Any]]:
        keep = ("uni_code", "course_code", "course_name", "university", "messages", "created_at", "updated_at")
        return [{k: c[k] for k in keep} for c in self.memory.store.conversations(user_id)]

    def chat_history(self, user_id: str, uni_code: str, before: int | None = None,
                     limit: int = 50) -> tuple[int, dict[str, Any]]:
        """One course chat's messages, oldest first: the newest `limit`, or those before seq `before`."""

        store = self.memory.store
        conversation = store.conversation(user_id, uni_code)
        if conversation is None:
            return 404, {"errors": [f"No chat for {uni_code}"]}
        messages = store.messages(conversation["id"], limit=limit + 1, before=before)
        more = len(messages) > limit
        return 200, {**{k: conversation[k] for k in ("uni_code", "course_code", "course_name", "university")},
                     "messages": messages[1:] if more else messages, "has_more": more}

    def delete_chat(self, user_id: str, uni_code: str) -> tuple[int, dict[str, Any]]:
        if not self.memory.store.delete_conversation(user_id, uni_code):
            return 404, {"errors": [f"No chat for {uni_code}"]}
        return 200, {"deleted": uni_code}

    def run(self, form: dict[str, Any], user_id: str | None = None) -> tuple[int, dict[str, Any]]:
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
        use_llm = bool(form.get("use_llm")) and (self.options["llm_available"]
                                                 or self.options["preference_ai_available"])
        try:
            suggestions = max(5, min(50, int(form.get("suggestions") or 20)))
        except (TypeError, ValueError):
            suggestions = 20
        if use_llm and (over := self.limits.check(user_id, "ai_recommendations")):
            return 429, {"errors": [over + " Untick \"Use AI\" to search without it."]}
        state = run_pipeline(inputs, self.pipeline(use_llm, suggestions))
        if state.get("errors"):
            return 400, {"errors": state["errors"]}
        if use_llm:
            self.limits.record(user_id, "ai_recommendations")
        if user_id:
            try:                                                # shown again after a reload / on another device
                self.memory.store.save_results(user_id, form, state["report"], use_llm)
            except Exception as exc:                            # the student still gets their results
                log.warning("could not save the results: %s", exc)
        return 200, {"report": state["report"], "used_llm": use_llm}
