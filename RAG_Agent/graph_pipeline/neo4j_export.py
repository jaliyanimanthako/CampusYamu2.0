"""Load the knowledge graph into Neo4j.

Two ways, both from ``generated/knowledge_graph.json``:

1. Write a Cypher script and run it with cypher-shell (or paste it into
   Neo4j Browser)::

       PYTHONPATH=. uv run python -m RAG_Agent.graph_pipeline.neo4j_export
       cypher-shell -u neo4j -p <password> -f RAG_Agent/generated/knowledge_graph.cypher

2. Push straight to a running database with the official driver::

       PYTHONPATH=. uv run --with neo4j python -m RAG_Agent.graph_pipeline.neo4j_export --push

   Connection settings come from the flags or from ``.env`` / the environment:
   ``NEO4J_URI``, ``NEO4J_USER``, ``NEO4J_PASSWORD``, ``NEO4J_DATABASE``. An
   empty password is asked for interactively.

Mapping: each node gets its ``type`` as label (Course, Institution, ...) plus
the shared label ``CampusKG``, and keeps its graph id in ``id``; each edge key
(HAS_REQUIREMENT, OFFERS_COURSE, ...) becomes the relationship type. Neo4j
properties cannot hold maps, so nested values (a requirement's ``rule``, an
offering's ``zscore_lookup``, ...) are stored as JSON strings.

Derived edges: ``(Stream)-[:CAN_APPLY_FOR]->(Course)`` is added for each
stream subject combination (owner_interpretations.json), computed by the
eligibility checker, because the A/L rules are stored as JSON that Cypher
cannot evaluate.

A load first deletes the existing ``CampusKG`` nodes, so re-running it replaces
the previous load and never touches other data in the database.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from itertools import combinations

import networkx as nx

from .build_graph import DEFAULT_OUTPUT, load_graph
from .eligibility import EligibilityChecker, make_student
from .handbook_prose import OWNER_INTERPRETATIONS, PROJECT_ROOT, _load_env

DEFAULT_CYPHER = Path("RAG_Agent/generated/knowledge_graph.cypher")
SHARED_LABEL = "CampusKG"
BATCH = 200
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DERIVED_CGT = 30            # the §1.2 minimum Common General Test mark
GRADE_LADDER = ("S", "C", "B", "A")

EXAMPLE_QUERIES = """\
// Example queries (Neo4j Browser):
// Everything one university offers
//   MATCH (i:Institution {name:'University of Moratuwa'})<-[:AT_INSTITUTION]-(o:Offering)-[:OFFERS_COURSE]->(c:Course)
//   RETURN i, o, c
// Where a course is offered, with its A/L requirements and citations
//   MATCH (c:Course {name:'Medicine'})-[r]-(n) RETURN c, r, n
// Courses whose requirements name a subject
//   MATCH (s:Subject {name:'Accounting'})<-[:NAMES_SUBJECT]-(q:Requirement)<-[:HAS_REQUIREMENT]-(c:Course)
//   RETURN c.name, q.evidence_text
// Courses a Physical Science student can apply for (derived by the eligibility checker)
//   MATCH (s:Stream {name:'Physical Science'})-[e:CAN_APPLY_FOR]->(c:Course)
//   RETURN c.code, c.name, e.lowest_grades, e.decision ORDER BY c.code
"""


# --- mapping ---------------------------------------------------------------
def _property(value: Any) -> Any:
    """A Neo4j-storable value: primitives, homogeneous primitive lists, else JSON text."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        items = [v for v in value if v is not None]
        kinds = {type(v) for v in items}
        if len(kinds) <= 1 and kinds <= {bool, int, float, str}:
            return list(items)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _properties(attrs: dict[str, Any], skip: Iterable[str] = ("type",)) -> dict[str, Any]:
    skipped = set(skip)
    out = {}
    for key, value in attrs.items():
        if key in skipped:
            continue
        stored = _property(value)
        if stored is not None and stored != []:
            out[key] = stored
    return out


def to_neo4j(graph: nx.MultiDiGraph) -> tuple[dict[str, list[dict]], dict[tuple[str, str, str], list[dict]]]:
    """Nodes grouped by label and relationships grouped by (type, source label, target label)."""

    nodes: dict[str, list[dict]] = defaultdict(list)
    for node, attrs in graph.nodes(data=True):
        nodes[attrs["type"]].append({"id": node, "props": {"id": node, **_properties(attrs)}})
    rels: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for source, target, key, attrs in graph.edges(keys=True, data=True):
        group = (key, graph.nodes[source]["type"], graph.nodes[target]["type"])
        rels[group].append({"source": source, "target": target, "props": _properties(attrs)})
    for label in {*nodes, *(name for group in rels for name in group)}:
        if not IDENTIFIER_RE.match(label):
            raise ValueError(f"Not a valid Neo4j label or relationship type: {label!r}")
    return dict(nodes), dict(rels)


def _batches(rows: list[dict], size: int = BATCH) -> Iterable[list[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def statements(graph: nx.MultiDiGraph) -> Iterable[tuple[str, dict[str, Any]]]:
    """Parameterised Cypher statements that (re)load the graph."""

    nodes, rels = to_neo4j(graph)
    for label in sorted(nodes):
        yield (f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
               f"FOR (n:{label}) REQUIRE n.id IS UNIQUE", {})
    yield f"MATCH (n:{SHARED_LABEL}) DETACH DELETE n", {}
    for label in sorted(nodes):
        for rows in _batches(nodes[label]):
            yield (f"UNWIND $rows AS row CREATE (n:{label}:{SHARED_LABEL}) SET n = row.props",
                   {"rows": rows})
    for (kind, source_label, target_label) in sorted(rels):
        for rows in _batches(rels[(kind, source_label, target_label)]):
            yield (f"UNWIND $rows AS row "
                   f"MATCH (a:{source_label} {{id: row.source}}) "
                   f"MATCH (b:{target_label} {{id: row.target}}) "
                   f"CREATE (a)-[r:{kind}]->(b) SET r = row.props",
                   {"rows": rows})
    for rows in _batches(stream_eligibility(graph)):
        yield ("UNWIND $rows AS row "
               "MATCH (a:Stream {id: row.source}) MATCH (b:Course {id: row.target}) "
               "CREATE (a)-[r:CAN_APPLY_FOR]->(b) SET r = row.props",
               {"rows": rows})
    # re-link handbook passages (RAG_Agent.handbook_search) to the reloaded sections
    yield ("MATCH (p:HandbookPassage) MATCH (s:HandbookSection {section_number: p.section_number}) "
           "MERGE (p)-[:IN_SECTION]->(s)", {})
    # re-link campuses (travel_time_agent) to the reloaded institutions
    yield ("MATCH (c:Campus) MATCH (i:Institution {id: c.institution_id}) "
           "MERGE (c)-[:CAMPUS_OF]->(i)", {})
    yield ("MATCH (c:Campus) MATCH (u:Institution {id: c.university_id}) "
           "MERGE (c)-[:OF_UNIVERSITY]->(u)", {})
    yield ("MATCH (c:Campus) UNWIND coalesce(c.taught_offerings, []) AS oid "
           "MATCH (o:Offering {id: oid}) MERGE (o)-[t:TAUGHT_AT]->(c) "
           "SET t.needs_review = oid IN coalesce(c.review_offerings, [])", {})


def stream_eligibility(graph: nx.MultiDiGraph,
                       interpretations: Path = OWNER_INTERPRETATIONS) -> list[dict[str, Any]]:
    """Derived (Stream)-[:CAN_APPLY_FOR]->(Course) rows for each stream subject combination.

    A course gets a row when a student with three of the stream's subjects
    (owner_interpretations.json ``stream_subjects``) and CGT 30 is eligible, or
    nothing fails but the handbook text needs checking. ``lowest_grades`` is the
    lowest uniform grade (S, C, B, A) that works.
    """

    streams = json.loads(Path(interpretations).read_text(encoding="utf-8"))
    streams = streams.get("stream_subjects", {}).get("streams", {})
    stream_ids = {a["name"]: n for n, a in graph.nodes(data=True) if a["type"] == "Stream"}
    checker = EligibilityChecker(graph)
    rows = []
    for stream, subjects in sorted(streams.items()):
        if stream not in stream_ids:
            continue
        for combo in combinations(subjects, 3):
            found: dict[str, tuple[str, str]] = {}
            for grade in GRADE_LADDER:
                student = make_student([f"{s}:{grade}" for s in combo], stream, DERIVED_CGT)
                for course in checker.courses:
                    if course in found:
                        continue
                    decision = checker.check_course(course, student).decision
                    if decision != "not_eligible":
                        found[course] = (grade, decision)
            for course, (grade, decision) in found.items():
                rows.append({"source": stream_ids[stream], "target": course, "props": {
                    "subjects": list(combo),
                    "lowest_grades": " ".join([grade] * 3),
                    "decision": decision,
                    "common_general_test": DERIVED_CGT,
                    "basis": "derived: eligibility checker over the graph's A/L rules",
                    "note": "Minimum requirements only; selection also depends on Z-score cut-offs.",
                }})
    return rows


# --- Cypher script -----------------------------------------------------------
def cypher_literal(value: Any) -> str:
    """A Cypher literal for a value produced by ``to_neo4j``."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        escaped = (value.replace("\\", "\\\\").replace("'", "\\'")
                   .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
        return f"'{escaped}'"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(cypher_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            name = key if IDENTIFIER_RE.match(key) else "`" + key.replace("`", "``") + "`"
            parts.append(f"{name}: {cypher_literal(item)}")
        return "{" + ", ".join(parts) + "}"
    raise TypeError(f"Cannot write {type(value).__name__} as Cypher")


def cypher_script(graph: nx.MultiDiGraph) -> str:
    lines = [
        "// CampusYamu admissions knowledge graph (UGC handbook "
        f"{graph.graph.get('academic_year', '')}).",
        f"// Generated by RAG_Agent.graph_pipeline.neo4j_export. Re-running replaces "
        f"all :{SHARED_LABEL} nodes.",
        EXAMPLE_QUERIES,
    ]
    for query, params in statements(graph):
        if "rows" in params:
            query = query.replace("$rows", cypher_literal(params["rows"]), 1)
        lines.append(query + ";")
    return "\n".join(lines) + "\n"


def write_cypher(graph: nx.MultiDiGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cypher_script(graph), encoding="utf-8")
    return path


# --- direct load ---------------------------------------------------------------
def push(graph: nx.MultiDiGraph, uri: str, user: str, password: str,
         database: str | None = None) -> dict[str, int]:
    try:
        from neo4j import GraphDatabase
        from neo4j.exceptions import AuthError, ServiceUnavailable
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("The neo4j driver is not installed; run with `uv run --with neo4j ...`") from exc
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        try:
            driver.verify_connectivity()
        except ServiceUnavailable as exc:
            raise SystemExit(
                f"Cannot reach Neo4j at {uri}: nothing is accepting connections.\n"
                "Start your instance in Neo4j Desktop (it must show 'Running'), then check its "
                "Bolt port matches NEO4J_URI in .env."
            ) from exc
        except AuthError as exc:
            raise SystemExit(f"Neo4j rejected user {user!r}: check NEO4J_PASSWORD in .env.") from exc
        with driver.session(database=database) as session:
            for query, params in statements(graph):
                session.run(query, params).consume()
            record = session.run(
                f"MATCH (n:{SHARED_LABEL}) WITH count(n) AS nodes "
                f"OPTIONAL MATCH (:{SHARED_LABEL})-[r]->(:{SHARED_LABEL}) "
                "RETURN nodes, count(r) AS relationships"
            ).single()
    return {"nodes": record["nodes"], "relationships": record["relationships"]}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the knowledge graph to Neo4j.")
    parser.add_argument("--graph", type=Path, default=PROJECT_ROOT / DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / DEFAULT_CYPHER,
                        help="Cypher script to write (when --uri is not given)")
    parser.add_argument("--push", action="store_true",
                        help="Load into the database named by NEO4J_URI instead of writing a script")
    parser.add_argument("--uri", help="Neo4j URI, e.g. neo4j://localhost:7687 (implies --push)")
    parser.add_argument("--user")
    parser.add_argument("--database", help="Database name (default: the server default)")
    parser.add_argument("--env-file", type=Path, help="Env file to read (default: ./.env)")
    args = parser.parse_args(argv)
    _load_env(args.env_file)
    graph = load_graph(args.graph)
    uri = args.uri or (os.environ.get("NEO4J_URI") if args.push else None)
    if args.push and not uri:
        parser.error("Set NEO4J_URI in .env or pass --uri")
    if uri:
        user = args.user or os.environ.get("NEO4J_USER") or "neo4j"
        database = args.database or os.environ.get("NEO4J_DATABASE") or None
        password = os.environ.get("NEO4J_PASSWORD") or getpass.getpass(f"Neo4j password for {user}: ")
        counts = push(graph, uri, user, password, database)
        print(f"Loaded {counts['nodes']} nodes and {counts['relationships']} relationships into {uri}")
        print(f"(graph has {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
        return 0
    path = write_cypher(graph, args.output)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB, {graph.number_of_nodes()} nodes, "
          f"{graph.number_of_edges()} relationships)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
