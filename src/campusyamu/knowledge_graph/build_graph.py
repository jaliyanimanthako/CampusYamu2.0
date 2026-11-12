"""Build the CampusYamu admissions knowledge graph (NetworkX MultiDiGraph).

Inputs are the checked pipeline outputs; nothing is extracted here:

* ``normalized_graph_data.json`` -- institutions, courses, offerings (UGC
  codes), O/L requirements, aptitude tests, intakes (table stages);
* ``handbook_structure.json`` -- stream sections and course-stream links;
* ``al_extraction_requests.json`` / ``al_rule_proposals.json`` -- A/L rules
  with their review status (only ``auto_accepted`` rules become requirements;
  other units attach their handbook text and mark the course incomplete);
* ``programme_requirements.json`` -- degree programmes and their requirements;
* ``reference/doe_al_subjects.json`` -- official A/L subjects and Arts baskets;
* ``reference/owner_interpretations.json`` -- owner stream-subject lists.

Every requirement node keeps its rule (executable by ``al_rule_semantics``),
its basis (deterministic_parser, model_consensus, owner_interpretation,
handbook_footnote, handbook_section) and a CITED_FROM edge to its handbook
section. Output: node-link JSON plus a validation report.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import networkx as nx

from .al_clause_parsers import OFFICIAL_SUBJECTS_PATH, canonical_stream, canonical_subject
from .handbook_prose import OWNER_INTERPRETATIONS, PROJECT_ROOT, _write_json
from .name_normalization import stable_slug

GENERATED = Path("data/processed/knowledge_graph")
HANDBOOK = Path("data/raw/handbook/student_handbook_english_structured.md")
DEFAULT_OUTPUT = GENERATED / "knowledge_graph.json"
DEFAULT_REPORT = GENERATED / "knowledge_graph_report.json"
SCHEMA_VERSION = 1

UNIVERSITY_MINIMUM_ID = "requirement:university-minimum"
ARTS_RULES_ID = "requirement:arts-selection-rules"
ARTS_COURSE_ID = "course:019"
# Units of section 2.2.1.1 that state the general Arts basket rules; their
# fragments are executed as one condition by ``arts_rules``.
ARTS_GENERAL_UNITS = {
    "al-extraction:2.2.1.1:general-core",
    "al-extraction:2.2.1.1:basket-1",
    "al-extraction:2.2.1.1:basket-2",
    "al-extraction:2.2.1.1:basket-3",
    "al-extraction:2.2.1.1:basket-4",
    "al-extraction:2.2.1.1:cross-basket-exceptions",
}
NON_EVALUATED_TYPES = {"other_admission_requirement"}


def _load(root: Path, path: Path) -> Any:
    return json.loads((root / path).read_text(encoding="utf-8"))


def al_subject_id(name: str) -> str:
    return f"subject:al:{stable_slug(name)}"


def stream_id(name: str) -> str:
    return f"stream:{stable_slug(name)}"


def section_id(number: str) -> str:
    return f"handbook-section:{number}"


def _empty_rule(target_id: str) -> dict[str, Any]:
    return {
        "target_type": "Course",
        "target_id": target_id,
        "eligible_streams": [],
        "subjects": [],
        "subject_groups": [],
        "minimum_grades": {
            "required_a_grades": 0,
            "required_b_grades": 0,
            "required_c_grades": 0,
            "required_s_grades": 0,
            "grade_condition_text": "",
        },
        "subject_grade_requirements": [],
        "common_general_paper": {"required": False, "minimum_percentage": 0, "condition": ""},
        "selection_constraints": [],
        "exception_to": "",
        "alternative_group": "",
        "alternative_option": 0,
        "conditions": [],
    }


def _page_of(lines: Sequence[str], line_number: int) -> int | None:
    for index in range(line_number - 1, -1, -1):
        match = re.match(r"<!-- PDF page (\d+) -->", lines[index].strip())
        if match:
            # A marker opens the page that follows it.
            return int(match.group(1))
    return None


def _university_minimum(lines: Sequence[str]) -> dict[str, Any]:
    heading = next(
        i for i, line in enumerate(lines, start=1)
        if line.strip() == "### 1.2 Minimum requirements for university admission"
    )
    clause_lines = [
        i for i, line in enumerate(lines, start=1)
        if heading < i < heading + 12 and line.strip().startswith(("- (a)", "- (b)"))
    ]
    if len(clause_lines) != 2:
        raise ValueError("Handbook section 1.2 clauses (a)/(b) not found")
    evidence = "\n".join(lines[i - 1].strip() for i in clause_lines)
    if "three approved subjects" not in evidence or "30%" not in evidence:
        raise ValueError("Handbook section 1.2 wording changed")
    rule = _empty_rule("*")
    rule["requirement_type"] = "al_minimum_grades"
    rule["minimum_grades"]["required_s_grades"] = 3
    rule["common_general_paper"] = {
        "required": True,
        "minimum_percentage": 30,
        "condition": "A minimum mark of 30% for the Common General Paper",
    }
    rule["conditions"] = [
        "In one sitting, within a maximum of three attempts (not checked from results)."
    ]
    return {
        "rule": rule,
        "evidence_text": evidence,
        "section": "1.2",
        "markdown_line_start": clause_lines[0],
        "markdown_line_end": clause_lines[-1],
        "pdf_page": _page_of(lines, clause_lines[0]),
    }


def _arts_rule() -> dict[str, Any]:
    rule = _empty_rule(ARTS_COURSE_ID)
    rule["requirement_type"] = "al_basket_rule"
    rule["eligible_streams"] = ["Arts"]
    rule["minimum_grades"]["required_s_grades"] = 3
    rule["selection_constraints"] = [
        {
            "constraint_type": "allowed_combination",
            "group_name": "Arts Stream subjects selected per Section 2.2.1.1",
            "subjects": [],
            "count": 3,
            "condition": "Basket rules and exceptions of Section 2.2.1.1",
        }
    ]
    return rule


def _subject_roles(rule: dict[str, Any]) -> list[tuple[str, str]]:
    roles: list[tuple[str, str]] = []
    for item in rule.get("subject_grade_requirements", []):
        options = [item.get("subject", ""), *item.get("alternatives", [])]
        role = "required" if len([o for o in options if o]) == 1 else "one_of"
        roles += [(name, f"{role}:{item.get('minimum_grade', 'S')}") for name in options if name]
    for group in rule.get("subject_groups", []):
        roles += [(name, "slot") for name in group.get("subjects", [])]
    for constraint in rule.get("selection_constraints", []):
        roles += [(name, str(constraint.get("constraint_type"))) for name in constraint.get("subjects", [])]
    for name in rule.get("subjects", []):
        roles.append((name, "named"))
    return roles


def build_graph(root: Path = PROJECT_ROOT) -> tuple[nx.MultiDiGraph, dict[str, Any]]:
    data = _load(root, GENERATED / "normalized_graph_data.json")
    structure = _load(root, GENERATED / "handbook_structure.json")
    requests = _load(root, GENERATED / "al_extraction_requests.json")["requests"]
    proposals = _load(root, GENERATED / "al_rule_proposals.json")
    programmes = _load(root, GENERATED / "programme_requirements.json")
    official = json.loads(OFFICIAL_SUBJECTS_PATH.read_text(encoding="utf-8"))
    owner = json.loads(OWNER_INTERPRETATIONS.read_text(encoding="utf-8"))
    lines = (root / HANDBOOK).read_text(encoding="utf-8").split("\n")

    graph = nx.MultiDiGraph(
        name="CampusYamu admissions knowledge graph",
        schema_version=SCHEMA_VERSION,
        academic_year=data["dataset"]["academic_year"],
    )
    problems: list[str] = []

    def add_edge(source: str, target: str, kind: str, **attrs: Any) -> None:
        for node in (source, target):
            if node not in graph:
                problems.append(f"{kind} edge references missing node {node}")
                return
        graph.add_edge(source, target, key=kind, type=kind, **attrs)

    def cite(node: str, number: str, **attrs: Any) -> None:
        sid = section_id(number)
        if sid not in graph:
            graph.add_node(sid, type="HandbookSection", section_number=number)
        add_edge(node, sid, "CITED_FROM", **attrs)

    # --- Institutions, courses, offerings, intakes ------------------------
    for item in data["institutions"]:
        graph.add_node(item["id"], type="Institution", name=item["name"],
                       institution_type=item["type"], aliases=item.get("aliases", []))
    for item in data["institutions"]:
        if item.get("parent_id"):
            add_edge(item["id"], item["parent_id"], "PART_OF")
    for item in data["courses"]:
        graph.add_node(item["id"], type="Course", name=item["name"], code=item["code"],
                       aliases=item.get("aliases", []))
    uni_codes = {item["offering_id"]: item["code"] for item in data["uni_codes"]}
    for item in data["course_offerings"]:
        graph.add_node(item["id"], type="Offering", uni_code=uni_codes.get(item["id"]),
                       academic_year_id=item["academic_year_id"],
                       zscore_lookup=item.get("zscore_lookup"))
        add_edge(item["id"], item["course_id"], "OFFERS_COURSE")
        add_edge(item["id"], item["institution_id"], "AT_INSTITUTION")
    for record in data["intake_records"]:
        if record["scope"] == "offering" and record["offering_id"] in graph:
            graph.nodes[record["offering_id"]]["proposed_intake"] = record["value"]
        elif record["scope"] == "course" and record["course_id"] in graph:
            graph.nodes[record["course_id"]][f"{record['category']}_intake"] = record["value"]

    # --- Streams, subjects, baskets ---------------------------------------
    for stream in structure["subject_streams"]:
        # "Courses open to multiple subject streams" (2.2.8) is a handbook
        # grouping of courses, not an A/L stream.
        is_stream = canonical_stream(stream["name"]) is not None
        graph.add_node(stream_id(stream["name"]), type="Stream" if is_stream else "CourseGroup",
                       name=stream["name"], handbook_section=stream["section_number"])
    stream_by_record = {s["id"]: stream_id(s["name"]) for s in structure["subject_streams"]}
    for link in structure["course_stream_links"]:
        target = stream_by_record[link["stream_id"]]
        kind = "LISTED_UNDER_STREAM" if graph.nodes[target]["type"] == "Stream" else "LISTED_IN_GROUP"
        add_edge(link["course_id"], target, kind)
    for basket in (1, 2, 3, 4):
        graph.add_node(f"arts-basket:{basket}", type="ArtsBasket", number=basket,
                       handbook_section="2.2.1.1")
    by_rule_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in official["subjects"] + official.get("old_syllabus_aliases", []):
        if item.get("rule_subject"):
            by_rule_subject[item["rule_subject"]].append(
                {"code": item["code"], "name": item["name"], "syllabus": item.get("syllabus", "current")}
            )
    baskets = {
        item["rule_subject"]: item.get("arts_basket")
        for item in official["subjects"] + official.get("handbook_only_subjects", [])
        if item.get("rule_subject")
    }
    from .al_clause_parsers import AL_SUBJECTS

    for name in AL_SUBJECTS:
        graph.add_node(al_subject_id(name), type="Subject", level="A/L", name=name,
                       official_subjects=by_rule_subject.get(name, []),
                       handbook_only=name not in by_rule_subject)
        if baskets.get(name):
            add_edge(al_subject_id(name), f"arts-basket:{baskets[name]}", "IN_ARTS_BASKET")
    lists = owner.get("stream_subjects", {})
    for stream_name, names in lists.get("streams", {}).items():
        sid = stream_id(stream_name)
        if sid not in graph:
            graph.add_node(sid, type="Stream", name=stream_name)
        for name in names:
            add_edge(al_subject_id(name), sid, "COUNTS_FOR_STREAM",
                     basis="owner_interpretation", decided_by=lists.get("decided_by"),
                     note=lists.get("basis"))
    for item in data["subjects"]:
        graph.add_node(item["id"], type="Subject", level=item["level"], name=item["name"])

    # --- University minimum and Arts rules --------------------------------
    minimum = _university_minimum(lines)
    graph.add_node(UNIVERSITY_MINIMUM_ID, type="Requirement", level="A/L",
                   requirement_type="al_minimum_grades", rule=minimum["rule"],
                   basis="handbook_section", evidence_text=minimum["evidence_text"],
                   evaluated=True)
    cite(UNIVERSITY_MINIMUM_ID, "1.2", markdown_line_start=minimum["markdown_line_start"],
         markdown_line_end=minimum["markdown_line_end"], pdf_page=minimum["pdf_page"])
    for course in data["courses"]:
        add_edge(course["id"], UNIVERSITY_MINIMUM_ID, "HAS_REQUIREMENT")
    graph.add_node(ARTS_RULES_ID, type="Requirement", level="A/L",
                   requirement_type="al_basket_rule", rule=_arts_rule(),
                   basis="handbook_section", executed_by="arts_rules.check_arts_combination",
                   evidence_text="Section 2.2.1.1 basket rules and exceptions", evaluated=True)
    cite(ARTS_RULES_ID, "2.2.1.1")
    add_edge(ARTS_COURSE_ID, ARTS_RULES_ID, "HAS_REQUIREMENT")
    for basket in (1, 2, 3, 4):
        add_edge(ARTS_RULES_ID, f"arts-basket:{basket}", "USES_BASKET")
    add_edge(ARTS_RULES_ID, stream_id("Arts"), "ALLOWS_STREAM")

    # --- A/L rules ---------------------------------------------------------
    results = {r["request_id"]: r for r in proposals["results"]}
    units_by_course: dict[str, list[str]] = defaultdict(list)
    for request in requests:
        for target in request["candidate_target_ids"]:
            units_by_course[target].append(request["id"])
    for request in requests:
        result = results.get(request["id"])
        accepted = result is not None and result.get("review_status") == "auto_accepted"
        if not accepted:
            text_id = f"handbook-text:{request['id']}"
            graph.add_node(
                text_id, type="HandbookText", request_id=request["id"],
                section_number=request["section_number"],
                review_status=(result or {}).get("review_status", "pending"),
                text=[c["text"] for c in request["eligibility_clauses"]
                      if c["scope_hint"] == "advanced_level_candidate"]
                or (result or {}).get("unresolved_text", []),
            )
            cite(text_id, request["section_number"])
            for target in request["candidate_target_ids"]:
                add_edge(target, text_id, "HAS_UNRESOLVED_REQUIREMENT_TEXT")
            continue
        for rule in result["rules"]:
            node = f"requirement:al:{rule['id']}"
            superseded = request["id"] in ARTS_GENERAL_UNITS
            evaluated = not superseded and rule["requirement_type"] not in NON_EVALUATED_TYPES
            graph.add_node(
                node, type="Requirement", level="A/L",
                requirement_type=rule["requirement_type"],
                rule={k: v for k, v in rule.items() if k not in {"id", "validation_status"}},
                basis=result.get("review_basis"),
                extraction_method=result.get("extraction_method"),
                interpretation=result.get("interpretation"),
                evidence_text=rule.get("evidence_text", ""),
                alternative_group=rule.get("alternative_group", ""),
                alternative_option=rule.get("alternative_option", 0),
                evaluated=evaluated,
                superseded_by=ARTS_RULES_ID if superseded else None,
                request_id=request["id"],
            )
            add_edge(rule["target_id"], node,
                     "HAS_REQUIREMENT" if not superseded else "HAS_REQUIREMENT_DETAIL")
            source = rule.get("source", {})
            cite(node, request["section_number"],
                 markdown_line_start=source.get("markdown_line_start"),
                 markdown_line_end=source.get("markdown_line_end"),
                 pdf_page=source.get("pdf_page"))
            for name, role in _subject_roles(rule):
                subject = canonical_subject(name)
                if subject:
                    add_edge(node, al_subject_id(subject), "NAMES_SUBJECT", role=role)
            for name in rule.get("eligible_streams", []):
                stream = canonical_stream(name)
                if stream and stream_id(stream) in graph:
                    add_edge(node, stream_id(stream), "ALLOWS_STREAM")
    for course in data["courses"]:
        units = units_by_course.get(course["id"], [])
        open_units = [u for u in units
                      if results.get(u, {}).get("review_status") != "auto_accepted"]
        graph.nodes[course["id"]]["al_requirement_units"] = units
        graph.nodes[course["id"]]["al_requirements_status"] = (
            "incomplete" if open_units or not units else "complete"
        )

    # --- O/L requirements and aptitude tests ------------------------------
    for item in data["requirements"]:
        graph.add_node(item["id"], type="Requirement", level=item["level"],
                       requirement_type=item["type"], minimum_grade=item["minimum_grade"],
                       basis="ugc_table", uni_code=item["uni_code"], evaluated=False)
        add_edge(item["offering_id"], item["id"], "HAS_REQUIREMENT")
        add_edge(item["id"], item["subject_id"], "ON_SUBJECT", minimum_grade=item["minimum_grade"])
    for item in data["aptitude_tests"]:
        graph.add_node(item["id"], type="AptitudeTest", required=item["required"],
                       uni_code=item["uni_code"])
        add_edge(item["offering_id"], item["id"], "REQUIRES_APTITUDE_TEST")
        if item.get("administered_by_institution_id"):
            add_edge(item["id"], item["administered_by_institution_id"], "ADMINISTERED_BY")

    # --- Degree programmes --------------------------------------------------
    for programme in programmes["programmes"]:
        graph.add_node(programme["id"], type="DegreeProgramme", name=programme["name"],
                       university=programme["university"],
                       course_resolved=len(programme["course_ids"]) == 1)
        cite(programme["id"], programme["section_number"],
             markdown_line_start=programme["markdown_line"], pdf_page=programme["pdf_page"])
        if programme["institution_id"]:
            add_edge(programme["id"], programme["institution_id"], "AT_INSTITUTION")
        for course_id in programme["course_ids"]:
            add_edge(programme["id"], course_id, "UNDER_COURSE",
                     resolved=len(programme["course_ids"]) == 1)
    for item in programmes["requirements"]:
        node = f"requirement:programme:{item['id']}"
        graph.add_node(node, type="Requirement", level="A/L", scope="programme",
                       requirement_type=item["rule"].get("requirement_type"),
                       rule={**_empty_rule(item["programme_id"]), **item["rule"]},
                       basis=item["review_basis"], interpretation=item.get("interpretation"),
                       evidence_text=item["evidence_text"], evaluated=True)
        add_edge(item["programme_id"], node, "HAS_REQUIREMENT")
        cite(node, item["source"]["section"], markdown_line_start=item["source"]["markdown_line"],
             pdf_page=item["source"].get("pdf_page"))
        for name, role in _subject_roles(item["rule"]):
            subject = canonical_subject(name)
            if subject:
                add_edge(node, al_subject_id(subject), "NAMES_SUBJECT", role=role)

    report = validate_graph(graph)
    report["problems"] = problems + report["problems"]
    report["status"] = "passed" if not report["problems"] else "failed"
    return graph, report


def validate_graph(graph: nx.MultiDiGraph) -> dict[str, Any]:
    problems: list[str] = []
    types = Counter(attrs["type"] for _, attrs in graph.nodes(data=True))
    edge_types = Counter(key for _, _, key in graph.edges(keys=True))
    courses = [n for n, a in graph.nodes(data=True) if a["type"] == "Course"]
    for course in courses:
        targets = {t for _, t, k in graph.out_edges(course, keys=True) if k == "HAS_REQUIREMENT"}
        if UNIVERSITY_MINIMUM_ID not in targets:
            problems.append(f"{course} lacks the university minimum")
        if not any(k == "OFFERS_COURSE" for _, _, k in graph.in_edges(course, keys=True)):
            problems.append(f"{course} has no offering")
    for node, attrs in graph.nodes(data=True):
        if attrs["type"] == "Requirement" and attrs.get("level") == "A/L":
            if not any(k == "CITED_FROM" for _, _, k in graph.out_edges(node, keys=True)):
                problems.append(f"{node} has no handbook citation")
    status = Counter(graph.nodes[c].get("al_requirements_status") for c in courses)
    return {
        "schema_version": SCHEMA_VERSION,
        "node_types": dict(sorted(types.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "courses_by_al_status": dict(status),
        "incomplete_courses": sorted(
            c for c in courses if graph.nodes[c].get("al_requirements_status") != "complete"
        ),
        "problems": problems,
    }


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    data = nx.node_link_data(graph, edges="edges")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_graph(path: Path = PROJECT_ROOT / DEFAULT_OUTPUT) -> nx.MultiDiGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return nx.node_link_graph(data, directed=True, multigraph=True, edges="edges")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the admissions knowledge graph.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    root = args.project_root.expanduser().resolve()
    graph, report = build_graph(root)
    save_graph(graph, root / args.output)
    _write_json(report, root / args.report)
    print(
        f"Knowledge graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges; "
        f"courses {report['courses_by_al_status']}; status {report['status']}"
        + (f"; {len(report['problems'])} problem(s), first: {report['problems'][0]}"
           if report["problems"] else "")
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
