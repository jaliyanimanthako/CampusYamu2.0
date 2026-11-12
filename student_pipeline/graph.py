"""Student pipeline as a LangGraph graph.

    START -> validate_profile -> find_courses
          -> (fan-out, in parallel) analyze_course x N  +  score_preferences
          -> assemble -> course_details -> rank_suggestions -> explain_rankings -> END

* ``validate_profile`` builds the StudentProfile and resolves the admission
  district and home town; invalid input ends the run with errors.
* ``find_courses`` is step 1 (course_finder): A/L eligibility from the KG,
  O/L requirements, aptitude tests and travel to each teaching site.
* After step 1, one ``analyze_course`` branch is sent per course (LangGraph
  ``Send``), running in parallel: the Z-score agent compares the student's
  Z-score with that course's historical cut-offs for the *admission district*
  and the result is matched to each eligible offering (university).
* ``score_preferences`` runs alongside: it reads the student's free-text
  interests ("engineering, design, planning") and gives every eligible course
  a 1-10 mark per interest: one LLM call, or the reviewed category marks in
  data/course_categories.json without an API key (preference_agent).
* ``assemble`` merges the branches into bands (strong / competitive / reach /
  unlikely / no history), nearest teaching site first within each band, and
  groups the same rows by the student's interests, highest mark first.

* ``course_details`` attaches each course's handbook facts for the course cards:
  degree programmes, duration, medium, notes (aptitude tests, selection by the
  faculty, ...) and the section text with its citation. Found by the course
  code in the handbook (course_details); no search or LLM.
* ``rank_suggestions`` (ranking_agent) builds the suggestion lists, 20 each:
  by Z-score analysis, by interests + last-year cut-off, and the same made
  distance-aware (far teaching sites pushed down). It also runs a what-if
  analysis on order 3 (re-ranking with interest / cut-off / distance x1.5).
* ``explain_rankings`` turns that analysis into feedback: a summary, a note per
  course and "if you care more about..." advice (one LLM call, or template
  sentences without an API key).

The LLM is used only to read the student's interests and to word the feedback;
every number and rank comes from
the KG, travel DB or Z-score DB.
Historical alignment is not an admission probability.
"""

from __future__ import annotations

import operator
import re
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from course_details import HandbookCourseIndex
from course_finder.finder import BLOCKED_OL, CourseFinder, ProfileError, StudentProfile
from preference_agent import Interpretation, Preference, PreferenceInterpreter, categorize, load_course_tags
from preference_agent.categorizer import DEFAULT_MIN_MARK
from ranking_agent import DEFAULT_LIMIT, build_rankings
from ranking_agent.feedback import FeedbackWriter
from ranking_agent.sensitivity import analyse
from zscore_agent import ZScoreAgent
from zscore_agent.models import ZScoreRequest
from zscore_agent.text import canonical_institution, normalized_text

# historical_alignment -> band shown to the student (best first)
BANDS = {
    "high": "strong",
    "medium_high": "strong",
    "medium": "competitive",
    "medium_low": "reach",
    "low": "unlikely",
}
BAND_ORDER = ["strong", "competitive", "reach", "unlikely", "no_history"]
INSTITUTION_NOISE = {"university", "of", "the", "sri", "lanka", "and", "&"}
SPELLING = {"swamy": "swami", "wickramaarachchi": "wickramarachchi"}


class PipelineState(TypedDict, total=False):
    inputs: dict[str, Any]                                   # raw student input
    profile: dict[str, Any]                                  # validated StudentProfile
    preferences: dict[str, Any]                              # interpreted interests (Interpretation)
    finder: dict[str, Any]                                   # step 1 result (FinderResult.to_dict)
    candidates: list[dict[str, Any]]                         # eligible offerings to analyse
    zscore_results: Annotated[list[dict[str, Any]], operator.add]   # filled by parallel branches
    report: dict[str, Any]
    errors: Annotated[list[str], operator.add]


class PreferenceTask(TypedDict):
    """The payload Send() gives the score_preferences branch."""

    text: str
    courses: list[str]


class CourseTask(TypedDict):
    """The payload Send() gives one analyze_course branch."""

    zscore_course: str
    offerings: list[dict[str, Any]]
    admission_district: str
    z_score: float
    stream: str


def _tokens(name: str) -> set[str]:
    words = re.findall(r"[a-z]+", normalized_text(name or ""))
    return {SPELLING.get(w, w) for w in words} - INSTITUTION_NOISE


def match_reports(offering_institution: str, reports: list[dict[str, Any]]) -> tuple[dict | None, str]:
    """The Z-score report for one university: exact name first, then a name variant.

    The cut-off tables spell some campuses differently across years ("Trincomalee
    Campus", "Eastern University - Trincomalee Campus"); a variant matches when
    all distinctive words of the KG name appear in it. Among several, the series
    with the most recent year wins.
    """

    wanted = normalized_text(canonical_institution(offering_institution or ""))
    exact = [r for r in reports if normalized_text(r["institution"] or "") == wanted]
    if exact:
        return exact[0], "exact"
    words = _tokens(offering_institution)
    variants = [r for r in reports if words and words <= _tokens(r["institution"] or "")]
    if not variants:
        return None, "none"
    variants.sort(key=lambda r: (r["historical_summary"]["latest_academic_year"],
                                 r["comparison"]["years_compared"]), reverse=True)
    return variants[0], "name_variant"


def build_pipeline(finder: CourseFinder | None = None, zscore: ZScoreAgent | None = None,
                   interpreter=None, use_llm: bool = True, min_mark: int = DEFAULT_MIN_MARK,
                   suggestions: int | None = DEFAULT_LIMIT, feedback_writer=None):
    finder = finder or CourseFinder()
    zscore = zscore or ZScoreAgent()
    tags = load_course_tags()
    interpreter = interpreter or PreferenceInterpreter(tags, use_llm=use_llm)
    feedback_writer = feedback_writer or FeedbackWriter(use_llm=use_llm)
    handbook = HandbookCourseIndex()
    lookups = {a["uni_code"]: a.get("zscore_lookup") or {}
               for _, a in finder.graph.nodes(data=True) if a["type"] == "Offering"}

    def nqc_note(task: CourseTask, offering: dict[str, Any]) -> str | None:
        """'NQC in every published year' when the series exists but has no numeric cut-off."""

        history = zscore.store.fetch_history(ZScoreRequest(
            district=task["admission_district"], course=task["zscore_course"],
            z_score=task["z_score"], stream=task["stream"]))
        wanted = normalized_text(canonical_institution(offering["zscore_institution"] or ""))
        years = sorted({m["academic_year"].replace("_", "/") for m in history.get("matches", [])
                        if normalized_text(m["institution"]) == wanted})
        values = {m["z_score"].casefold() for m in history.get("matches", [])
                  if normalized_text(m["institution"]) == wanted}
        if years and values == {"nqc"}:
            return (f"NQC (no qualified candidates selected) from {task['admission_district']} district "
                    f"in every published year ({years[0]}–{years[-1]}); no numeric cut-off to compare")
        return None

    # --- nodes ------------------------------------------------------------------------
    def validate_profile(state: PipelineState) -> dict[str, Any]:
        try:
            fields = {k: v for k, v in state["inputs"].items() if k != "preferences"}
            profile = StudentProfile.from_inputs(**fields)
            district = finder.resolve_admission_district(profile.admission_district)
            finder.resolve_origin(profile.home)
        except (ProfileError, TypeError, ValueError) as exc:
            hint = getattr(exc, "suggestions", None)
            return {"errors": [str(exc) + (f" (did you mean: {', '.join(hint[:6])}?)" if hint else "")]}
        profile.admission_district = district
        return {"profile": {**profile.__dict__, "student_stream": profile.stream}}

    def score_preferences(task: PreferenceTask) -> dict[str, Any]:
        return {"preferences": interpreter.interpret(task["text"], task["courses"]).to_dict()}

    def find_courses(state: PipelineState) -> dict[str, Any]:
        fields = {k: v for k, v in state["profile"].items() if k != "student_stream"}
        result = finder.find_courses(StudentProfile(**fields)).to_dict()
        stream = result["profile"].get("student_stream_resolved") or state["profile"]["stream"]
        candidates = []
        for group in ("can_apply", "with_conditions"):
            for course in result["groups"][group]:
                for offering in course["offerings"]:
                    if offering["status"] == BLOCKED_OL:
                        continue
                    lookup = lookups.get(offering["uni_code"], {})
                    candidates.append({**offering, "course_code": course["course_code"],
                                       "course_name": course["name"], "group": group,
                                       "zscore_course": lookup.get("course"),
                                       "zscore_institution": lookup.get("institution")})
        return {"finder": result, "candidates": candidates,
                "profile": {**state["profile"], "student_stream": stream}}

    def analyze_course(task: CourseTask) -> dict[str, Any]:
        analysis = zscore.analyze(district=task["admission_district"], course=task["zscore_course"],
                                  z_score=task["z_score"], limit=200, stream=task["stream"])
        reports = analysis.get("reports", [])
        out = []
        for offering in task["offerings"]:
            report, matched_by = match_reports(offering["zscore_institution"], reports)
            if report is None:
                out.append({**offering, "band": "no_history", "matched_by": "none",
                            "zscore_status": analysis["status"],
                            "zscore_note": nqc_note(task, offering) or analysis.get("message")})
                continue
            summary, comparison = report["historical_summary"], report["comparison"]
            out.append({
                **offering,
                "band": BANDS[report["historical_alignment"]],
                "matched_by": matched_by,
                "zscore_series": f"{report['course']} — {report['institution']}",
                "historical_alignment": report["historical_alignment"],
                "evidence_confidence": report["evidence_confidence"],
                "predicted_cutoff": comparison["predicted_cutoff"],
                "uncertainty": comparison["uncertainty"],
                "expected_margin": comparison["expected_margin"],
                "years_met": comparison["years_met_or_exceeded"],
                "years_compared": comparison["years_compared"],
                "latest_cutoff": summary["latest_cutoff"],
                "latest_year": summary["latest_academic_year"],
                "forecast_year": comparison["forecast_academic_year"],
                "reason": report["reason"],
            })
        return {"zscore_results": out}

    def assemble(state: PipelineState) -> dict[str, Any]:
        profile = state["profile"]
        results = state.get("zscore_results") or []
        analysed = {r["uni_code"] for r in results}
        skipped = [{**c, "band": "no_history", "matched_by": "none",
                    "zscore_note": "no Z-score given" if profile.get("z_score") is None
                    else "no cut-off table name for this offering"}
                   for c in state.get("candidates", []) if c["uni_code"] not in analysed]
        rows = results + skipped

        def order(r):
            return (BAND_ORDER.index(r["band"]), r.get("car_min") or 1e9, r["uni_code"])

        raw = state.get("preferences") or {"text": "", "method": "none"}
        interpretation = Interpretation(**{**raw, "preferences": []})
        interpretation.preferences = [Preference(**p) for p in raw.get("preferences", [])]
        rows, preferences = categorize(rows, interpretation, tags, sort_key=order, min_mark=min_mark)
        rows.sort(key=order)
        bands = {band: [r for r in rows if r["band"] == band] for band in BAND_ORDER}
        return {"report": {
            "profile": profile,
            "origin": state["finder"]["origin"],
            "counts": {**state["finder"]["counts"], **{f"band_{b}": len(v) for b, v in bands.items()}},
            "preferences": preferences,
            "bands": bands,
            "notes": state["finder"]["notes"][1:] + [
                f"Z-score comparison uses the {profile['admission_district']} district cut-offs "
                "(admission district, handbook §1.5).",
                "Bands come from the Z-score agent's historical alignment: strong = high/medium-high, "
                "competitive = medium, reach = medium-low, unlikely = low. They are not admission "
                "probabilities or guarantees.",
            ],
        }}

    def course_details(state: PipelineState) -> dict[str, Any]:
        report = state["report"]
        details: dict[str, Any] = {}
        bands = {}
        for band, rows in report["bands"].items():
            out = []
            for row in rows:
                code = row.get("course_code") or ""
                if code not in details:
                    details[code] = {"course_name": row.get("course_name"),
                                     "blocks": [b.to_dict() for b in handbook.blocks_for(code)]}
                out.append({**row, "details_block": handbook.block_for_offering(
                    code, row.get("university"), row.get("site"))})
            bands[band] = out
        return {"report": {**report, "bands": bands, "course_details": details}}

    def rank_suggestions(state: PipelineState) -> dict[str, Any]:
        report = state["report"]
        rankings = build_rankings(report, suggestions)
        rows = [row for band in report["bands"].values() for row in band]
        rankings["distance"] = {**rankings["distance"], "analysis": analyse(rows, suggestions)}
        return {"report": {**report, "rankings": rankings}}

    def explain_rankings(state: PipelineState) -> dict[str, Any]:
        report = state["report"]
        profile, origin = report["profile"], report["origin"]
        context = {"stream": profile.get("stream"), "z_score": profile.get("z_score"),
                   "admission_district": profile.get("admission_district"),
                   "home": f"{origin['ds_division']} ({origin['district']} district)",
                   "interests": (report.get("preferences") or {}).get("text")}
        distance = report["rankings"]["distance"]
        feedback = feedback_writer.write(distance["analysis"], context)
        rankings = {**report["rankings"], "distance": {**distance, "feedback": feedback}}
        return {"report": {**report, "rankings": rankings}}

    # --- routing ------------------------------------------------------------------------
    def after_validation(state: PipelineState) -> str:
        return END if state.get("errors") else "find_courses"

    def fan_out(state: PipelineState):
        profile = state["profile"]
        sends = []
        text = state["inputs"].get("preferences") or ""
        if isinstance(text, (list, tuple)):
            text = ", ".join(t for t in text if t)
        if text.strip():
            courses = sorted({c["course_code"] for c in state["candidates"]})
            sends.append(Send("score_preferences", PreferenceTask(text=text, courses=courses)))
        tasks: dict[str, list[dict]] = {}
        if profile.get("z_score") is not None:
            for candidate in state["candidates"]:
                if candidate.get("zscore_course"):
                    tasks.setdefault(candidate["zscore_course"], []).append(candidate)
        sends += [Send("analyze_course", CourseTask(zscore_course=course, offerings=offerings,
                                                    admission_district=profile["admission_district"],
                                                    z_score=profile["z_score"],
                                                    stream=profile["student_stream"]))
                  for course, offerings in tasks.items()]
        return sends or "assemble"

    graph = StateGraph(PipelineState)
    graph.add_node("validate_profile", validate_profile)
    graph.add_node("find_courses", find_courses)
    graph.add_node("score_preferences", score_preferences)
    graph.add_node("analyze_course", analyze_course)
    graph.add_node("assemble", assemble)
    graph.add_node("course_details", course_details)
    graph.add_node("rank_suggestions", rank_suggestions)
    graph.add_node("explain_rankings", explain_rankings)
    graph.add_edge(START, "validate_profile")
    graph.add_conditional_edges("validate_profile", after_validation, ["find_courses", END])
    graph.add_conditional_edges("find_courses", fan_out, ["analyze_course", "score_preferences", "assemble"])
    graph.add_edge("analyze_course", "assemble")
    graph.add_edge("score_preferences", "assemble")
    graph.add_edge("assemble", "course_details")
    graph.add_edge("course_details", "rank_suggestions")
    graph.add_edge("rank_suggestions", "explain_rankings")
    graph.add_edge("explain_rankings", END)
    return graph.compile()


def run_pipeline(inputs: dict[str, Any], app=None) -> PipelineState:
    """Run once and return the final state (``report`` or ``errors``)."""

    app = app or build_pipeline()
    return app.invoke({"inputs": inputs, "zscore_results": [], "errors": []})
