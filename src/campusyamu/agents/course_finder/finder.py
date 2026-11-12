"""Step 1 of the student pipeline: which courses can this student apply for?

Input is a ``StudentProfile`` (stream, three A/L subjects with grades, Common
General Test mark, admission district, home town / DS division, O/L grades,
optional Z-score).

The admission district (the "district of a candidate for university
admission", handbook §1.5, decided by school enrolment) and the home town are
independent: a student may sit the exam from a school in another district.
The admission district is validated and carried for the Z-score step; the
home town is used only for travel times. They are never cross-checked. Everything is read from the knowledge graph and the travel
database; nothing is guessed:

* A/L eligibility per course   -- EligibilityChecker over the graph's rules
  (university minimum §1.2, course rules, Arts basket rules), with citations
* O/L requirements per offering -- the UGC O/L table nodes in the graph
* aptitude tests, extra conditions (e.g. Nursing height), programme-level
  requirements (e.g. Accounting for finance degrees)
* travel from the student's DS division to the site where each offering is
  taught (agents.travel_time)

The Z-score is carried in the profile but not used here: cut-off comparison
is the next pipeline step.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from campusyamu.knowledge_graph.al_clause_parsers import canonical_subject
from campusyamu.knowledge_graph.build_graph import DEFAULT_OUTPUT, load_graph
from campusyamu.knowledge_graph.eligibility import EligibilityChecker, make_student
from campusyamu.knowledge_graph.handbook_prose import PROJECT_ROOT
from campusyamu.agents.travel_time.build_db import DEFAULT_DB
from campusyamu.agents.travel_time.repository import LookupError_, Origin, TravelRepository

DEFAULT_GRAPH = PROJECT_ROOT / DEFAULT_OUTPUT
OL_GRADES = {"A": 4, "B": 3, "C": 2, "S": 1, "W": 0}
OL_SUBJECTS = {
    "science": "Science",
    "english": "English",
    "maths": "Mathematics",
    "math": "Mathematics",
    "mathematics": "Mathematics",
    "sinhala": "Sinhala Language and Literature",
    "sinhala language and literature": "Sinhala Language and Literature",
    "tamil": "Tamil Language and Literature",
    "tamil language and literature": "Tamil Language and Literature",
}

# Handbook alternatives to an O/L requirement: course code -> (O/L subject it replaces,
# A/L subject that satisfies it instead, minimum A/L grade, citation, A/L subjects whose
# standing is unclear and must be confirmed rather than assumed).
OL_ALTERNATIVES = {
    code: ("Mathematics", "Mathematics", "S", citation, ("Combined Mathematics", "Higher Mathematics"))
    for code, citation in (("023", "Handbook §2.2.8.6, line 4613"),
                           ("097", "Handbook §2.2.8.8, line 4773"),
                           ("024", "Handbook §2.2.8.9, line 4803"))
}
AL_GRADES = {"A": 4, "B": 3, "C": 2, "S": 1, "F": 0}

# offering status, best first
OPEN = "open"                        # A/L + O/L met, nothing else needed
APTITUDE = "aptitude_test"           # also needs the university's aptitude test
CHECK_OL = "check_ol"                # needs an O/L grade the student did not give
BLOCKED_OL = "blocked_ol"            # an O/L requirement is not met
STATUS_ORDER = [OPEN, APTITUDE, CHECK_OL, BLOCKED_OL]


class ProfileError(ValueError):
    def __init__(self, message: str, suggestions: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.suggestions = list(suggestions)


def parse_grade_items(items: Sequence[str], what: str) -> list[tuple[str, str]]:
    """'Combined Mathematics:A' / 'Combined Mathematics A' -> (name, grade)."""

    parsed = []
    for raw in items:
        text = str(raw).strip()
        if ":" in text:
            name, _, grade = text.rpartition(":")
        else:
            name, _, grade = text.rpartition(" ")
        name, grade = name.strip(), grade.strip().upper()
        if not name or not grade:
            raise ProfileError(f"Give each {what} as 'Subject:Grade', got {raw!r}")
        parsed.append((name, grade))
    return parsed


def normalize_ol(items: Sequence[str]) -> dict[str, str]:
    grades: dict[str, str] = {}
    for name, grade in parse_grade_items(items, "O/L result"):
        subject = OL_SUBJECTS.get(name.casefold())
        if subject is None:
            raise ProfileError(f"Unknown O/L subject {name!r}",
                               sorted(set(OL_SUBJECTS.values())))
        grade = "W" if grade == "F" else grade
        if grade not in OL_GRADES:
            raise ProfileError(f"O/L grade for {subject} must be A, B, C, S or W, got {grade!r}")
        grades[subject] = grade
    return grades


@dataclass
class StudentProfile:
    stream: str
    al_results: list[tuple[str, str]]          # [(subject, grade)] x 3
    common_general_test: int
    admission_district: str                    # §1.5 district used for selection / Z-score cut-offs
    home: str                                  # DS division or its main town (travel only)
    ol_results: dict[str, str]                 # {"English": "B", ...}
    z_score: float | None = None

    @classmethod
    def from_inputs(cls, *, stream: str, al: Sequence[str], cgt: int, admission_district: str, home: str,
                    ol: Sequence[str], z_score: float | None = None) -> "StudentProfile":
        if not 0 <= int(cgt) <= 100:
            raise ProfileError("Common General Test mark must be between 0 and 100")
        results = []
        for name, grade in parse_grade_items(al, "A/L result"):
            subject = canonical_subject(name)
            if subject is None:
                raise ProfileError(f"Unknown A/L subject {name!r}")
            if grade not in AL_GRADES:
                raise ProfileError(f"A/L grade for {subject} must be A, B, C, S or F, got {grade!r}")
            results.append((subject, grade))
        return cls(stream, results, int(cgt), admission_district, home, normalize_ol(ol), z_score)


@dataclass
class Offering:
    uni_code: str
    university: str | None
    site: str | None
    site_district: str | None
    proposed_intake: int | None
    status: str
    ol_met: list[str] = field(default_factory=list)
    ol_failed: list[str] = field(default_factory=list)
    ol_unknown: list[str] = field(default_factory=list)
    aptitude_test: bool = False
    car_min: float | None = None
    bus_min_est: float | None = None
    road_km: float | None = None
    same_district: bool | None = None
    site_to_confirm: bool = False
    approximate_location: bool = False


@dataclass
class CourseMatch:
    course_code: str
    name: str
    decision: str                               # eligible | check_handbook | not_eligible
    offerings: list[Offering] = field(default_factory=list)
    additional_conditions: list[str] = field(default_factory=list)
    programmes_not_open: list[str] = field(default_factory=list)
    unresolved_text: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)   # why not eligible (with citations)

    @property
    def best_status(self) -> str | None:
        statuses = [o.status for o in self.offerings]
        return min(statuses, key=STATUS_ORDER.index) if statuses else None

    @property
    def nearest_min(self) -> float:
        times = [o.car_min for o in self.offerings if o.status != BLOCKED_OL and o.car_min is not None]
        return min(times) if times else float("inf")


@dataclass
class FinderResult:
    profile: dict[str, Any]
    origin: dict[str, Any]
    courses: list[CourseMatch]
    notes: list[str]

    def by_group(self) -> dict[str, list[CourseMatch]]:
        groups: dict[str, list[CourseMatch]] = {
            "can_apply": [], "with_conditions": [], "check_handbook": [], "blocked_by_ol": [],
            "not_eligible": []}
        for course in self.courses:
            if course.decision == "not_eligible":
                groups["not_eligible"].append(course)
            elif course.decision == "check_handbook":
                groups["check_handbook"].append(course)
            elif course.best_status == BLOCKED_OL:
                groups["blocked_by_ol"].append(course)
            elif course.best_status == OPEN and not course.additional_conditions:
                groups["can_apply"].append(course)
            else:
                groups["with_conditions"].append(course)
        for name, items in groups.items():
            items.sort(key=(lambda c: c.name) if name == "not_eligible" else (lambda c: (c.nearest_min, c.name)))
        return groups

    def to_dict(self) -> dict[str, Any]:
        groups = self.by_group()
        return {
            "profile": self.profile, "origin": self.origin, "notes": self.notes,
            "counts": {k: len(v) for k, v in groups.items()},
            "groups": {k: [{**asdict(c), "best_status": c.best_status} for c in v]
                       for k, v in groups.items()},
        }


class CourseFinder:
    def __init__(self, graph_path: Path = DEFAULT_GRAPH, travel_db: Path = DEFAULT_DB) -> None:
        self.graph = load_graph(graph_path)
        self.checker = EligibilityChecker(self.graph)
        self.travel = TravelRepository(travel_db)

    def close(self) -> None:
        self.travel.close()

    # --- profile resolution -------------------------------------------------------
    def resolve_admission_district(self, name: str) -> str:
        """One of the 25 districts (typos fixed); not compared with the home town."""

        try:
            return self.travel._district(name)
        except LookupError_ as exc:
            raise ProfileError(f"Unknown admission district {name!r}", exc.suggestions) from None

    def resolve_origin(self, home: str) -> Origin:
        """The home DS division anywhere in Sri Lanka (DS division names are unique)."""

        try:
            return self.travel.find_origin(home)
        except LookupError_ as exc:
            raise ProfileError(str(exc), exc.suggestions) from None

    # --- the step -------------------------------------------------------------------
    def find_courses(self, profile: StudentProfile) -> FinderResult:
        try:
            student = make_student([f"{s}:{g}" for s, g in profile.al_results],
                                   profile.stream, profile.common_general_test)
        except ValueError as exc:
            raise ProfileError(str(exc)) from None
        admission_district = self.resolve_admission_district(profile.admission_district)
        origin = self.resolve_origin(profile.home)
        travel = {r["uni_code"]: r for r in self.travel.course_offerings(origin)}

        courses = []
        for result in self.checker.check_all(student):
            course = CourseMatch(
                course_code=self.graph.nodes[result.course_id]["code"], name=result.name,
                decision=result.decision,
                additional_conditions=list(result.additional_conditions),
                programmes_not_open=[f"{p['programme']} ({p['university']})"
                                     for p in result.programme_requirements if not p["met"]],
                unresolved_text=list(result.unresolved_text),
                reasons=[self._reason(f) for f in result.failed],
            )
            if result.decision != "not_eligible":
                course.offerings = sorted(
                    (self._offering(node, profile, course.course_code, travel)
                     for node in self._in(result.course_id, "OFFERS_COURSE")),
                    key=lambda o: (STATUS_ORDER.index(o.status) == 3, o.car_min if o.car_min is not None else 1e9))
            courses.append(course)

        notes = [
            "Eligibility = the handbook's minimum requirements. Selection also depends on Z-score "
            "cut-offs, which this step does not apply" + (
                f" (Z-score {profile.z_score} recorded for the next step)." if profile.z_score is not None else "."),
            "Car = free-flow driving time by road; bus ≈ rough public-transport estimate.",
        ]
        return FinderResult(
            profile={**asdict(profile), "admission_district": admission_district,
                     "student_stream_resolved": student.stream},
            origin=asdict(origin), courses=courses, notes=notes)

    # --- helpers --------------------------------------------------------------------
    def _in(self, node: str, kind: str) -> list[str]:
        return [s for s, _, k in self.graph.in_edges(node, keys=True) if k == kind]

    def _out(self, node: str, kind: str) -> list[str]:
        return [t for _, t, k in self.graph.out_edges(node, keys=True) if k == kind]

    @staticmethod
    def _reason(finding) -> str:
        text = " ".join((finding.evidence_text or "").split())
        text = text if len(text) <= 220 else text[:217] + "…"
        extra = f" [{'; '.join(finding.reasons)}]" if finding.reasons else ""
        return f"{finding.citation}: {text}{extra}"

    def _offering(self, node: str, profile: StudentProfile, course_code: str,
                  travel: dict[str, dict]) -> Offering:
        attrs = self.graph.nodes[node]
        ol = profile.ol_results
        al = dict(profile.al_results)
        alternative = OL_ALTERNATIVES.get(course_code)
        met, failed, unknown = [], [], []
        for requirement in self._out(node, "HAS_REQUIREMENT"):
            req = self.graph.nodes[requirement]
            if req.get("level") != "O/L":
                continue
            need = req["minimum_grade"]
            for subject_node in self._out(requirement, "ON_SUBJECT"):
                subject = self.graph.nodes[subject_node]["name"]
                text = f"O/L {subject} ≥ {need}"
                if subject in ol and OL_GRADES[ol[subject]] >= OL_GRADES[need]:
                    met.append(text)
                    continue
                if alternative and alternative[0] == subject:
                    _, al_subject, al_need, citation, unclear = alternative
                    if al.get(al_subject) and AL_GRADES[al[al_subject]] >= AL_GRADES[al_need]:
                        met.append(f"{text} — met instead by A/L {al_subject} {al[al_subject]} ({citation})")
                        continue
                    held = [s for s in unclear if s in al]
                    if held:
                        unknown.append(f"{text}, or A/L {al_subject} ≥ {al_need} ({citation}): "
                                       f"confirm whether A/L {held[0]} counts")
                        continue
                if subject not in ol:
                    unknown.append(text)
                else:
                    failed.append(f"{text} (you have {ol[subject]})")
        aptitude = bool(self._out(node, "REQUIRES_APTITUDE_TEST"))
        status = BLOCKED_OL if failed else CHECK_OL if unknown else APTITUDE if aptitude else OPEN
        t = travel.get(attrs["uni_code"], {})
        return Offering(
            uni_code=attrs["uni_code"], university=t.get("university"), site=t.get("campus_site"),
            site_district=t.get("campus_district"), proposed_intake=attrs.get("proposed_intake"),
            status=status, ol_met=met, ol_failed=failed, ol_unknown=unknown, aptitude_test=aptitude,
            car_min=t.get("drive_min"), bus_min_est=t.get("bus_min_est"), road_km=t.get("road_km"),
            same_district=bool(t["same_district"]) if t else None,
            site_to_confirm=bool(t.get("site_needs_review")),
            approximate_location=bool(t.get("approximate_location")),
        )
