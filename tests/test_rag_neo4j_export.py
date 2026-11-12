from __future__ import annotations

import json
import unittest

from RAG_Agent.graph_pipeline.build_graph import DEFAULT_OUTPUT, load_graph
from RAG_Agent.graph_pipeline.neo4j_export import (
    SHARED_LABEL,
    cypher_literal,
    cypher_script,
    statements,
    stream_eligibility,
    to_neo4j,
)
from RAG_Agent.graph_pipeline.source_registry import PROJECT_ROOT

PRIMITIVES = (bool, int, float, str)


class Neo4jExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = load_graph(PROJECT_ROOT / DEFAULT_OUTPUT)
        cls.nodes, cls.rels = to_neo4j(cls.graph)

    def test_every_node_and_edge_is_exported_with_storable_properties(self) -> None:
        self.assertEqual(sum(map(len, self.nodes.values())), self.graph.number_of_nodes())
        self.assertEqual(sum(map(len, self.rels.values())), self.graph.number_of_edges())
        rows = [r["props"] for group in (*self.nodes.values(), *self.rels.values()) for r in group]
        for props in rows:
            for key, value in props.items():
                ok = isinstance(value, PRIMITIVES) or (
                    isinstance(value, list) and len({type(v) for v in value}) == 1
                    and isinstance(value[0], PRIMITIVES)
                )
                self.assertTrue(ok, f"{key}={value!r} is not a Neo4j property value")

    def test_nested_rules_survive_as_json(self) -> None:
        requirement = next(
            r for r in self.nodes["Requirement"] if "rule" in self.graph.nodes[r["id"]]
        )
        self.assertEqual(json.loads(requirement["props"]["rule"]),
                         self.graph.nodes[requirement["id"]]["rule"])

    def test_load_replaces_only_its_own_nodes(self) -> None:
        queries = [q for q, _ in statements(self.graph)]
        deletes = [q for q in queries if "DELETE" in q]
        self.assertEqual(deletes, [f"MATCH (n:{SHARED_LABEL}) DETACH DELETE n"])
        self.assertLess(queries.index(deletes[0]),
                        min(i for i, q in enumerate(queries) if q.startswith("UNWIND")))

    def test_string_literals_are_escaped(self) -> None:
        self.assertEqual(cypher_literal("it's a \\ back\nslash"), r"'it\'s a \\ back\nslash'")
        self.assertEqual(cypher_literal({"id": "x", "odd key": [1, True, None]}),
                         "{id: 'x', `odd key`: [1, true, null]}")

    def test_script_has_one_statement_per_query(self) -> None:
        script = cypher_script(self.graph)
        self.assertEqual(script.count(";\n"), sum(1 for _ in statements(self.graph)))
        self.assertNotIn("$rows", script)

    def test_physical_science_can_apply_for_edges(self) -> None:
        rows = [r for r in stream_eligibility(self.graph) if r["source"] == "stream:physical-science"]
        names = {self.graph.nodes[r["target"]]["name"]: r["props"]["lowest_grades"] for r in rows}
        self.assertEqual(len(names), 55)
        self.assertEqual(names["Engineering"], "S S S")
        self.assertEqual(names["Architecture"], "S S S")          # owner reading of §2.2.8.6
        self.assertEqual(names["Computer Science"], "C C C")
        self.assertNotIn("Medicine", names)


if __name__ == "__main__":
    unittest.main()
