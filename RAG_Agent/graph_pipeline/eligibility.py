"""Course eligibility from the knowledge graph, with reasons and citations.

Given a student's three A/L subjects and grades, stream and Common General
Test mark, every course is checked against the A/L requirement nodes the
graph links to it (university minimum, course rules, Arts basket rules) and
answered with one of:

* ``eligible`` -- every evaluated requirement is met and the course's A/L
  requirements are complete;
* ``not_eligible`` -- an evaluated requirement fails (with its handbook quote);
* ``check_handbook`` -- nothing failed, but part of the course's A/L
  requirement is unresolved; its handbook text is returned instead of a guess.

Requirements that are not about A/L results (O/L grades, aptitude tests, the
Nursing height condition) are listed as additional conditions, as are
programme-level requirements (e.g. Accounting for finance programmes).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import networkx as nx

from .al_clause_parsers import canonical_stream, canonical_subject
from .al_rule_semantics import NotEvaluable, Student, evaluate_rules
from .arts_rules import check_arts_combination
from .build_graph import ARTS_RULES_ID, DEFAULT_OUTPUT, load_graph
from .handbook_prose import PROJECT_ROOT

GRADES = ("A", "B", "C", "S", "F")


def make_student(subjects: Sequence[str], stream: str | None, cgp: int) -> Student:
    """Build a student from 'Subject:Grade' items using official or handbook names."""

    grades = []
    for item in subjects:
        name, _, grade = str(item).rpartition(":") if ":" in str(item) else (item, "", "S")
        subject = canonical_subject(name)
        if subject is None:
            raise ValueError(f"Unknown A/L subject: {name!r}")
        grade = (grade or "S").upper()
        if grade not in GRADES:
            raise ValueError(f"Unknown grade {grade!r} for {subject}")
        grades.append((subject, grade))
    if len(grades) != 3:
        raise ValueError("Give exactly three A/L subjects")
    resolved_stream = canonical_stream(stream) if stream else None
    if stream and resolved_stream is None:
        raise ValueError(f"Unknown stream: {stream!r}")
    return Student(tuple(grades), resolved_stream, int(cgp))


@dataclass
class Finding:
    requirement_id: str
    evidence_text: str
    citation: str
    basis: str | None
    reasons: list[str] = field(default_factory=list)


@dataclass
class CourseResult:
    course_id: str
    name: str
    decision: str
    failed: list[Finding] = field(default_factory=list)
    unresolved_text: list[str] = field(default_factory=list)
    additional_conditions: list[str] = field(default_factory=list)
    programme_requirements: list[dict[str, Any]] = field(default_factory=list)
    offerings: list[dict[str, Any]] = field(default_factory=list)


class EligibilityChecker:
    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self.graph = graph
        self.courses = sorted(n for n, a in graph.nodes(data=True) if a["type"] == "Course")

    # --- graph access ------------------------------------------------------
    def _out(self, node: str, kind: str) -> list[str]:
        return [t for _, t, k in self.graph.out_edges(node, keys=True) if k == kind]

    def _in(self, node: str, kind: str) -> list[str]:
        return [s for s, _, k in self.graph.in_edges(node, keys=True) if k == kind]

    def _citation(self, node: str) -> str:
        for _, target, key, attrs in self.graph.out_edges(node, keys=True, data=True):
            if key == "CITED_FROM":
                section = self.graph.nodes[target].get("section_number")
                page = attrs.get("pdf_page")
                start = attrs.get("markdown_line_start")
                return f"Handbook §{section}" + (f", p. {page}" if page else "") + (
                    f", line {start}" if start else ""
                )
        return "Handbook"

    # --- checks --------------------------------------------------------------
    def _check_rules(self, nodes: Sequence[str], student: Student) -> list[Finding]:
        """Evaluate mandatory rules one by one and alternative groups as a whole."""

        failed: list[Finding] = []
        groups: dict[str, dict[int, list[str]]] = {}
        for node in nodes:
            attrs = self.graph.nodes[node]
            group = attrs.get("alternative_group") or ""
            if group:
                groups.setdefault(group, {}).setdefault(attrs.get("alternative_option", 0), []).append(node)
                continue
            if not evaluate_rules([attrs["rule"]], student):
                failed.append(self._finding(node, student))
        for options in groups.values():
            if not any(
                evaluate_rules([self.graph.nodes[n]["rule"] for n in option], student)
                for option in options.values()
            ):
                first = next(iter(options.values()))[0]
                finding = self._finding(first, student)
                finding.reasons.append(
                    f"None of the {len(options)} alternative options is satisfied"
                )
                failed.append(finding)
        return failed

    def _finding(self, node: str, student: Student) -> Finding:
        attrs = self.graph.nodes[node]
        reasons: list[str] = []
        if node == ARTS_RULES_ID:
            if student.stream != "Arts":
                reasons.append("Requires the Arts stream")
            reasons += list(check_arts_combination(student.passed()).reasons)
        return Finding(node, attrs.get("evidence_text", ""), self._citation(node),
                       attrs.get("basis"), reasons)

    def check_course(self, course_id: str, student: Student) -> CourseResult:
        course = self.graph.nodes[course_id]
        result = CourseResult(course_id, course["name"], "eligible")
        evaluated: list[str] = []
        for node in self._out(course_id, "HAS_REQUIREMENT"):
            attrs = self.graph.nodes[node]
            if attrs.get("level") != "A/L":
                continue
            if attrs.get("evaluated"):
                evaluated.append(node)
            else:
                result.additional_conditions += [
                    f"{text} ({self._citation(node)})" for text in attrs["rule"].get("conditions", [])
                ] or [f"{attrs.get('evidence_text', '')} ({self._citation(node)})"]
        try:
            result.failed = self._check_rules(evaluated, student)
        except NotEvaluable as exc:  # pragma: no cover - guarded by graph build
            result.decision = "check_handbook"
            result.unresolved_text.append(f"Could not evaluate: {exc}")
        for text_node in self._out(course_id, "HAS_UNRESOLVED_REQUIREMENT_TEXT"):
            result.unresolved_text += list(self.graph.nodes[text_node].get("text", []))
        if result.failed:
            result.decision = "not_eligible"
        elif result.unresolved_text or course.get("al_requirements_status") != "complete":
            result.decision = "check_handbook"

        result.offerings = self.offerings(course_id)

        for programme in self._in(course_id, "UNDER_COURSE"):
            for node in self._out(programme, "HAS_REQUIREMENT"):
                attrs = self.graph.nodes[node]
                met = evaluate_rules([attrs["rule"]], student)
                result.programme_requirements.append(
                    {
                        "programme": self.graph.nodes[programme]["name"],
                        "university": self.graph.nodes[programme]["university"],
                        "met": met,
                        "evidence_text": attrs.get("evidence_text"),
                        "basis": attrs.get("basis"),
                    }
                )
        return result

    def offerings(self, course_id: str) -> list[dict[str, Any]]:
        """Universities offering a course, with UGC code, intake, O/L and aptitude needs."""

        entries = []
        for offering in self._in(course_id, "OFFERS_COURSE"):
            attrs = self.graph.nodes[offering]
            institution = self._out(offering, "AT_INSTITUTION")
            entries.append({
                "uni_code": attrs.get("uni_code"),
                "institution": self.graph.nodes[institution[0]]["name"] if institution else None,
                "proposed_intake": attrs.get("proposed_intake"),
                "ol_requirements": [
                    f"O/L {self.graph.nodes[s]['name']} at least {self.graph.nodes[r]['minimum_grade']}"
                    for r in self._out(offering, "HAS_REQUIREMENT")
                    for s in self._out(r, "ON_SUBJECT")
                ],
                "aptitude_test": bool(self._out(offering, "REQUIRES_APTITUDE_TEST")),
            })
        return sorted(entries, key=lambda o: o["uni_code"] or "")

    def check_all(self, student: Student) -> list[CourseResult]:
        return [self.check_course(course, student) for course in self.courses]


def _summary(results: Sequence[CourseResult], offerings: bool = False) -> str:
    lines: list[str] = []
    for decision, title in (
        ("eligible", "Eligible"),
        ("check_handbook", "Check the handbook (requirement text not fully resolved)"),
    ):
        chosen = [r for r in results if r.decision == decision]
        lines.append(f"\n{title}: {len(chosen)}")
        for r in chosen:
            extra = []
            if r.additional_conditions:
                extra.append("+ " + "; ".join(r.additional_conditions)[:120])
            if any(o["ol_requirements"] for o in r.offerings):
                extra.append("+ O/L requirements at some universities")
            if any(o["aptitude_test"] for o in r.offerings):
                extra.append("+ aptitude test")
            unmet = [p for p in r.programme_requirements if not p["met"]]
            if unmet:
                extra.append(f"+ {len(unmet)} programme(s) need more (e.g. {unmet[0]['programme']})")
            lines.append(f"  {r.name} [{r.course_id}] " + " ".join(extra))
            if offerings:
                for o in r.offerings:
                    notes = []
                    if o["ol_requirements"]:
                        notes.append("; ".join(o["ol_requirements"]))
                    if o["aptitude_test"]:
                        notes.append("aptitude test")
                    intake = f", intake {o['proposed_intake']}" if o.get("proposed_intake") else ""
                    lines.append(f"      - {o['uni_code']} {o['institution']}{intake}"
                                 + (f"  ({' | '.join(notes)})" if notes else ""))
                for prog in r.programme_requirements:
                    if not prog["met"]:
                        lines.append(f"      ! not open: {prog['programme']} ({prog['university']})")
    lines.append(f"\nNot eligible: {sum(r.decision == 'not_eligible' for r in results)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check course eligibility from the knowledge graph.")
    parser.add_argument("--subject", action="append", required=True,
                        help="A/L subject and grade, e.g. 'Combined Mathematics:A' (three times)")
    parser.add_argument("--stream")
    parser.add_argument("--cgp", type=int, default=30, help="Common General Test mark (default 30)")
    parser.add_argument("--course", help="Explain one course (id like course:001 or a name)")
    parser.add_argument("--graph", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--offerings", action="store_true",
                        help="Also list universities, UGC codes, intakes and extra conditions")
    args = parser.parse_args(argv)
    checker = EligibilityChecker(load_graph(args.graph))
    try:
        student = make_student(args.subject, args.stream, args.cgp)
    except ValueError as exc:
        parser.error(str(exc))
    if args.course:
        wanted = args.course.casefold()
        course = next(
            (c for c in checker.courses
             if c == args.course or checker.graph.nodes[c]["name"].casefold() == wanted),
            None,
        )
        if course is None:
            parser.error(f"Unknown course: {args.course}")
        result = checker.check_course(course, student)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    results = checker.check_all(student)
    if args.json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
    else:
        print(_summary(results, offerings=args.offerings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
