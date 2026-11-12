"""Degree programmes and programme-level A/L requirements.

Some handbook units list, per university, the degree programmes offered under
one or more courses, and state requirements for *some* of those programmes
rather than for the whole course:

* a sentence such as "To enter into some degree programmes such as
  Accountancy, Auditing & Forensic Accounting and Finance ..., students should
  have offered Accounting" -- applied through an owner rule in
  ``reference/owner_interpretations.json`` (``programme_rules``), because the
  handbook only gives examples ("such as");
* a footnote in a university's list ("**_Student must have passed ..._**")
  that applies to that university's programmes marked with "*".

These clauses are tagged ``excluded_programme_level`` in the A/L ledger, so
they never become course rules. This module turns them into requirement
records in the A/L rule format (``evaluate_rules`` can execute them), attached
to programme records that carry their university and handbook line.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Sequence

from .handbook_prose import (
    DEFAULT_REQUESTS,
    OWNER_INTERPRETATIONS,
    PROGRAMME_LIST_RE,
    PROJECT_ROOT,
    _write_json,
)
from .name_normalization import lookup_key, stable_slug

DEFAULT_GRAPH_DATA = Path("RAG_Agent/generated/normalized_graph_data.json")
DEFAULT_OUTPUT = Path("RAG_Agent/generated/programme_requirements.json")
UNIVERSITY_HEADING_RE = re.compile(r"^#+\s*_(?P<name>.+?)_\s*$")
PROGRAMME_RE = re.compile(r"^-\s+(?P<name>Bachelor\b.+?)\s*(?P<marker>\*?)\s*$")
FOOTNOTE_RE = re.compile(r"^-\s+\*\*_(?P<text>.+?)_\*\*\s*$")


def _empty_rule() -> dict[str, Any]:
    return {
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
    }


def _grade_item(subject: str, alternatives: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "subject": subject,
        "minimum_grade": "S",
        "alternatives": list(alternatives),
        "condition": "",
    }


# Footnotes recognised exactly; anything else is kept as text only.
_COMMERCE_FOOTNOTE_RE = re.compile(
    r"^Student must have passed G\.C\.E\. \(Advanced Level\) in Commerce Stream covering "
    r"Accounting and Economics together with Business Studies or Business Statistics\.?$"
)


def _footnote_rule(text: str) -> dict[str, Any] | None:
    if not _COMMERCE_FOOTNOTE_RE.match(text):
        return None
    return {
        **_empty_rule(),
        "requirement_type": "al_stream_eligibility",
        "eligible_streams": ["Commerce"],
        "subject_grade_requirements": [
            _grade_item("Accounting"),
            _grade_item("Economics"),
            _grade_item("Business Studies", ["Business Statistics"]),
        ],
    }


def _institution_ids(graph_data: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    for item in graph_data.get("institutions", []):
        for key in [item["name"], *item.get("aliases", []), *item.get("search_keys", [])]:
            ids[lookup_key(key)] = item["id"]
    return ids


def parse_programme_lists(
    requests: Sequence[dict[str, Any]], graph_data: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (programmes, footnotes) from units with a university/programme list."""

    institutions = _institution_ids(graph_data)
    programmes: list[dict[str, Any]] = []
    footnotes: list[dict[str, Any]] = []
    for request in requests:
        started = False
        university: str | None = None
        for line in request["evidence_lines"]:
            text = str(line["text"]).strip()
            if not text or text.startswith("<!--"):
                continue
            if PROGRAMME_LIST_RE.search(text):
                started = True
                continue
            if not started:
                continue
            heading = UNIVERSITY_HEADING_RE.match(text)
            if heading:
                university = " ".join(heading.group("name").split())
                continue
            if university is None:
                continue
            key = lookup_key(university)
            # "Trincomalee Campus of the Eastern University, Sri Lanka" is
            # registered as "Trincomalee Campus, Eastern University, Sri Lanka".
            institution_id = institutions.get(key) or institutions.get(
                key.replace(" of the ", " ")
            )
            footnote = FOOTNOTE_RE.match(text)
            if footnote:
                footnotes.append(
                    {
                        "section_number": request["section_number"],
                        "university": university,
                        "institution_id": institution_id,
                        "text": " ".join(footnote.group("text").split()),
                        "markdown_line": int(line["markdown_line"]),
                        "pdf_page": line["pdf_page"],
                    }
                )
                continue
            programme = PROGRAMME_RE.match(text)
            if programme:
                name = " ".join(programme.group("name").split())
                programmes.append(
                    {
                        "id": (
                            f"programme:{request['section_number']}:"
                            f"{stable_slug(university)}:{stable_slug(name)}"
                        ),
                        "name": name,
                        "university": university,
                        "institution_id": institution_id,
                        "footnote_marker": programme.group("marker") or "",
                        "section_number": request["section_number"],
                        # The list covers every course of the unit; the handbook
                        # does not say which course each programme belongs to.
                        "course_ids": list(request["candidate_target_ids"]),
                        "markdown_line": int(line["markdown_line"]),
                        "pdf_page": line["pdf_page"],
                    }
                )
    return programmes, footnotes


def build_programme_requirements(
    requests: Sequence[dict[str, Any]],
    graph_data: dict[str, Any],
    owner_rules: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    programmes, footnotes = parse_programme_lists(requests, graph_data)
    evidence = {
        (request["section_number"], int(line["markdown_line"])): str(line["text"]).strip()
        for request in requests
        for line in request["evidence_lines"]
    }
    requirements: list[dict[str, Any]] = []
    unmatched_footnotes: list[dict[str, Any]] = []

    for rule in owner_rules:
        pattern = re.compile(rule["programme_name_pattern"], re.IGNORECASE)
        quote = evidence.get((rule["section_number"], int(rule["source_line"])))
        if quote is None:
            raise ValueError(f"Owner programme rule {rule['id']} cites a missing line")
        sections = set(rule.get("applies_to_sections") or [rule["section_number"]])
        for programme in programmes:
            if programme["section_number"] not in sections:
                continue
            if not pattern.search(programme["name"]):
                continue
            requirements.append(
                {
                    "id": f"{programme['id']}:{rule['id']}",
                    "programme_id": programme["id"],
                    "rule": {**_empty_rule(), **rule["requirement"]},
                    "review_status": "auto_accepted",
                    "review_basis": "owner_interpretation",
                    "interpretation": {
                        key: rule[key]
                        for key in ("id", "reading", "decided_by", "date",
                                    "programme_name_pattern", "applies_to_sections")
                        if key in rule
                    },
                    "evidence_text": quote,
                    "source": {
                        "section": rule["section_number"],
                        "markdown_line": int(rule["source_line"]),
                    },
                }
            )

    for footnote in footnotes:
        rule = _footnote_rule(footnote["text"])
        marked = [
            programme
            for programme in programmes
            if programme["section_number"] == footnote["section_number"]
            and programme["university"] == footnote["university"]
            and programme["footnote_marker"] == "*"
        ]
        if rule is None or not marked:
            unmatched_footnotes.append(footnote)
            continue
        for programme in marked:
            requirements.append(
                {
                    "id": f"{programme['id']}:footnote-{footnote['markdown_line']}",
                    "programme_id": programme["id"],
                    "rule": rule,
                    "review_status": "auto_accepted",
                    "review_basis": "handbook_footnote",
                    "evidence_text": footnote["text"],
                    "source": {
                        "section": footnote["section_number"],
                        "markdown_line": footnote["markdown_line"],
                        "pdf_page": footnote["pdf_page"],
                    },
                }
            )

    return {
        "schema_version": 1,
        "generation_stage": "programme_requirements",
        "notes": [
            "Programme-level requirements apply in addition to the course's A/L rules.",
            "course_ids lists every course of the unit; the handbook does not map each "
            "programme to one course.",
        ],
        "programme_count": len(programmes),
        "requirement_count": len(requirements),
        "programmes": programmes,
        "requirements": requirements,
        "unmatched_footnotes": unmatched_footnotes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--graph-data", type=Path, default=DEFAULT_GRAPH_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    root = args.project_root.expanduser().resolve()
    requests = json.loads((root / args.requests).read_text(encoding="utf-8"))["requests"]
    graph_data = json.loads((root / args.graph_data).read_text(encoding="utf-8"))
    owner = json.loads(OWNER_INTERPRETATIONS.read_text(encoding="utf-8"))
    output = build_programme_requirements(
        requests, graph_data, owner.get("programme_rules", [])
    )
    _write_json(output, root / args.output)
    unresolved = sorted(
        {p["university"] for p in output["programmes"] if p["institution_id"] is None}
    )
    print(
        f"Parsed {output['programme_count']} degree programmes; "
        f"{output['requirement_count']} programme-level requirements; "
        f"unmatched footnotes: {len(output['unmatched_footnotes'])}; "
        f"unresolved universities: {unresolved or 'none'}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
