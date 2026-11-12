"""Write the knowledge graph browser: a self-contained HTML dashboard.

    PYTHONPATH=. uv run python -m RAG_Agent.graph_pipeline.graph_viewer
    open RAG_Agent/generated/knowledge_graph_viewer.html

A Neo4j-Browser-style page (template ``templates/viewer.html``) drawn with
force-graph (2D canvas, animated force layout, loaded from jsDelivr): label and
relationship-type pills with counts, search, a properties inspector with the
handbook quote and citation, double-click to expand, right-click to hide.
No server or database is needed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .build_graph import DEFAULT_OUTPUT, load_graph
from .handbook_prose import PROJECT_ROOT

DEFAULT_HTML = Path("RAG_Agent/generated/knowledge_graph_viewer.html")
FORCE_GRAPH_URL = "https://cdn.jsdelivr.net/npm/force-graph@1.51.4/dist/force-graph.min.js"
TEMPLATE = Path(__file__).with_name("templates") / "viewer.html"


def summarize_rule(rule: dict[str, Any]) -> list[str]:
    """Plain-language lines for a stored A/L rule."""

    lines: list[str] = []
    if rule.get("eligible_streams"):
        lines.append("Stream: " + " or ".join(rule["eligible_streams"]))
    grades = rule.get("minimum_grades", {})
    counts = [
        f"{grades.get(f'required_{g.lower()}_grades')} × {g}"
        for g in "ABCS"
        if grades.get(f"required_{g.lower()}_grades")
    ]
    if counts:
        lines.append("Grades: at least " + ", ".join(counts))
    for item in rule.get("subject_grade_requirements", []):
        options = [o for o in [item.get("subject"), *item.get("alternatives", [])] if o]
        lines.append(f"{item.get('minimum_grade', 'S')} or better in " + " or ".join(options))
    for group in rule.get("subject_groups", []):
        high = group.get("maximum_allowed") or "any"
        lines.append(
            f"{group.get('minimum_required')}–{high} from: " + ", ".join(group.get("subjects", []))
        )
    for constraint in rule.get("selection_constraints", []):
        subjects = ", ".join(constraint.get("subjects", [])) or constraint.get("group_name", "")
        lines.append(f"{constraint.get('constraint_type')} ({constraint.get('count')}): {subjects}")
    cgp = rule.get("common_general_paper", {}) or {}
    if cgp.get("required"):
        lines.append(f"Common General Test ≥ {cgp.get('minimum_percentage')}%")
    if rule.get("alternative_group"):
        lines.append(f"Option {rule.get('alternative_option')} of '{rule['alternative_group']}' (OR)")
    for text in rule.get("conditions", []):
        if rule.get("requirement_type") == "other_admission_requirement":
            lines.append("Condition: " + text)
    return lines


def _label(node: str, attrs: dict[str, Any]) -> str:
    kind = attrs["type"]
    if kind == "Offering":
        return attrs.get("uni_code") or node
    if kind == "HandbookSection":
        return f"§{attrs.get('section_number')}"
    if kind == "ArtsBasket":
        return f"Basket {attrs.get('number')}"
    if kind == "Requirement":
        if node == "requirement:university-minimum":
            return "University minimum (§1.2)"
        if node == "requirement:arts-selection-rules":
            return "Arts basket rules (§2.2.1.1)"
        if attrs.get("level") == "O/L":
            return f"O/L ≥ {attrs.get('minimum_grade')}"
        text = (attrs.get("evidence_text") or attrs.get("requirement_type") or "").strip()
        return (text[:48] + "…") if len(text) > 48 else text
    if kind == "HandbookText":
        return f"Unresolved text §{attrs.get('section_number')}"
    if kind == "AptitudeTest":
        return f"Aptitude test {attrs.get('uni_code')}"
    return str(attrs.get("name") or node)


def _details(node: str, attrs: dict[str, Any]) -> dict[str, Any]:
    keep = {
        "Course": ["code", "total_proposed_intake", "additional_intake", "al_requirements_status"],
        "Offering": ["uni_code", "proposed_intake"],
        "Institution": ["institution_type"],
        "Subject": ["level"],
        "DegreeProgramme": ["university", "course_resolved"],
        "Requirement": ["level", "requirement_type", "basis", "extraction_method", "evaluated"],
        "AptitudeTest": ["uni_code", "required"],
        "HandbookText": ["review_status", "section_number"],
        "Stream": ["handbook_section"],
        "CourseGroup": ["handbook_section"],
    }.get(attrs["type"], [])
    out: dict[str, Any] = {
        key: attrs[key] for key in keep if attrs.get(key) not in (None, "", [])
    }
    if attrs["type"] == "Subject" and attrs.get("official_subjects"):
        out["official"] = "; ".join(
            f"{item['code']} {item['name']}" for item in attrs["official_subjects"]
        )
    if attrs.get("rule"):
        out["rule"] = summarize_rule(attrs["rule"])
    if attrs.get("evidence_text"):
        out["handbook text"] = attrs["evidence_text"]
    if attrs.get("interpretation"):
        out["owner reading"] = attrs["interpretation"].get("reading")
    if attrs.get("text"):
        out["handbook text"] = "\n".join(attrs["text"])
    return out


def build_payload(graph) -> dict[str, Any]:
    groups: dict[str, str] = {}
    for source, target, key in graph.edges(keys=True):
        if key in {"LISTED_UNDER_STREAM", "LISTED_IN_GROUP"}:
            groups[source] = graph.nodes[target]["name"]
    nodes = []
    for node, attrs in graph.nodes(data=True):
        nodes.append({
            "id": node,
            "type": attrs["type"],
            "label": _label(node, attrs),
            "details": _details(node, attrs),
            "group": groups.get(node) or (attrs.get("name") if attrs["type"] in {"Stream", "CourseGroup"} else None),
            "intake": attrs.get("total_proposed_intake") or attrs.get("proposed_intake"),
        })
    edges = []
    for index, (source, target, key, attrs) in enumerate(graph.edges(keys=True, data=True)):
        extra = {k: v for k, v in attrs.items() if k != "type" and v not in (None, "", [])}
        edges.append({"id": f"e{index}", "source": source, "target": target, "type": key,
                      "attrs": extra})
    return {"nodes": nodes, "edges": edges,
            "meta": {"academic_year": graph.graph.get("academic_year")}}


def render_viewer(graph, chat: bool = False) -> str:
    """The page as a string; ``chat=True`` when served by chat_server (same origin API)."""

    data = json.dumps(build_payload(graph), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__FORCE_GRAPH__", FORCE_GRAPH_URL)
    html = html.replace("__CHAT_SERVED__", "true" if chat else "false")
    return html.replace("__DATA__", data)


def write_viewer(graph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_viewer(graph), encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the knowledge graph browser page.")
    parser.add_argument("--graph", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / DEFAULT_HTML)
    args = parser.parse_args(argv)
    path = write_viewer(load_graph(args.graph), args.output)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB). Open it in a browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
