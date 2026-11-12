"""Handbook passages and chunks in Neo4j, beside the knowledge graph.

    (:HandbookPassage:CampusDocs)  parent: a handbook section (or part of one)
    (:HandbookChunk:CampusDocs)    child: embedded + full-text indexed
    (chunk)-[:CHUNK_OF]->(passage)-[:IN_SECTION]->(:HandbookSection)   # KG node, when it exists
    (passage)-[:NEXT_PASSAGE]->(passage)                               # reading order

Indexes:
    handbook_chunk_embedding  vector index (cosine) on HandbookChunk.embedding
    handbook_chunk_text       full-text (Lucene, BM25 scoring, English analyzer)
                              on HandbookChunk.embed_text

Loading replaces every ``CampusDocs`` node and never touches the KG
(``CampusKG``) nodes; the KG export re-creates the IN_SECTION links after a
KG reload.
"""

from __future__ import annotations

import os
import re
from typing import Any, Sequence

from .embeddings import vector_for

DOCS_LABEL = "CampusDocs"
VECTOR_INDEX = "handbook_chunk_embedding"
TEXT_INDEX = "handbook_chunk_text"
BATCH = 100
LINK_SECTIONS = (
    "MATCH (p:HandbookPassage) MATCH (s:HandbookSection {section_number: p.section_number}) "
    "MERGE (p)-[:IN_SECTION]->(s)"
)
LUCENE_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def connect(uri: str | None = None, user: str | None = None, password: str | None = None):
    """A neo4j driver from arguments or NEO4J_* environment variables (.env)."""

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SystemExit("The neo4j driver is not installed (uv sync)") from exc
    uri = uri or os.environ.get("NEO4J_URI")
    if not uri:
        raise SystemExit("Set NEO4J_URI in .env (e.g. neo4j://127.0.0.1:7687)")
    password = password or os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("Set NEO4J_PASSWORD in .env")
    return GraphDatabase.driver(uri, auth=(user or os.environ.get("NEO4J_USER") or "neo4j", password),
                                notifications_min_severity="OFF")


def lucene_query(text: str) -> str:
    """A safe Lucene query: the words of ``text`` ORed.

    Special characters are dropped and words lowercased, so a user's "AND",
    "OR" or "NOT" can never act as an operator. Single letters are kept (the
    "Z" in Z-score, grade "S").
    """

    return " OR ".join(w.lower() for w in LUCENE_WORD_RE.findall(text))


class HandbookStore:
    def __init__(self, driver, database: str | None = None) -> None:
        self.driver = driver
        self.database = database or os.environ.get("NEO4J_DATABASE") or None
        self._search_clause: bool | None = None     # None = not tried yet

    def _run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        records, _, _ = self.driver.execute_query(cypher, params, database_=self.database)
        return [dict(r) for r in records]

    # --- loading ----------------------------------------------------------------
    def load(self, chunks: dict, cache: dict, model: str) -> dict[str, int]:
        children = []
        missing = 0
        for child in chunks["children"]:
            vector = vector_for(cache, model, child["embed_text"])
            if vector is None:
                missing += 1
                continue
            children.append({**child, "embedding": vector})
        if missing:
            raise SystemExit(f"{missing} chunks have no {model} embedding; run the embed step first")
        dimensions = len(children[0]["embedding"]) if children else 0
        parents = chunks["parents"]

        self._run(f"MATCH (n:{DOCS_LABEL}) DETACH DELETE n")
        for label in ("HandbookPassage", "HandbookChunk"):
            self._run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                      f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
        for start in range(0, len(parents), BATCH):
            self._run(
                f"UNWIND $rows AS row CREATE (p:HandbookPassage:{DOCS_LABEL}) SET p = row",
                rows=parents[start:start + BATCH],
            )
        self._run(
            "MATCH (p:HandbookPassage) WITH p ORDER BY p.line_start "
            "WITH collect(p) AS ps UNWIND range(0, size(ps) - 2) AS i "
            "WITH ps[i] AS a, ps[i + 1] AS b CREATE (a)-[:NEXT_PASSAGE]->(b)"
        )
        for start in range(0, len(children), BATCH):
            self._run(
                f"UNWIND $rows AS row CREATE (c:HandbookChunk:{DOCS_LABEL}) SET c = row "
                "WITH c, row MATCH (p:HandbookPassage {id: row.parent_id}) CREATE (c)-[:CHUNK_OF]->(p)",
                rows=children[start:start + BATCH],
            )
        self._run(LINK_SECTIONS)

        # indexes are rebuilt so a different embedding model (dimensions) never clashes
        self._run(f"DROP INDEX {VECTOR_INDEX} IF EXISTS")
        self._run(f"DROP INDEX {TEXT_INDEX} IF EXISTS")
        self._run(
            f"CREATE VECTOR INDEX {VECTOR_INDEX} FOR (c:HandbookChunk) ON c.embedding "
            "OPTIONS {indexConfig: {`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}}",
            dims=dimensions,
        )
        self._run(
            f"CREATE FULLTEXT INDEX {TEXT_INDEX} FOR (c:HandbookChunk) ON EACH [c.embed_text] "
            "OPTIONS {indexConfig: {`fulltext.analyzer`: 'english'}}"
        )
        self._run("CALL db.awaitIndexes(300)")
        counts = self._run(
            "MATCH (p:HandbookPassage) WITH count(p) AS passages "
            "MATCH (c:HandbookChunk) WITH passages, count(c) AS chunks "
            "OPTIONAL MATCH (:HandbookPassage)-[r:IN_SECTION]->() "
            "RETURN passages, chunks, count(r) AS linked_to_kg"
        )[0]
        return {**counts, "dimensions": dimensions}

    # --- searching ----------------------------------------------------------------
    def vector_search(self, vector: Sequence[float], k: int) -> list[dict[str, Any]]:
        params = {"k": k, "vector": list(vector)}
        if self._search_clause is not False:
            try:
                rows = self._run(
                    "MATCH (c:HandbookChunk) "
                    f"SEARCH c IN (VECTOR INDEX {VECTOR_INDEX} FOR $vector LIMIT $k) SCORE AS score "
                    "RETURN c.id AS id, score ORDER BY score DESC",
                    **params,
                )
                self._search_clause = True
                return rows
            except Exception as exc:  # servers before the SEARCH clause (Neo4j < 2026.x)
                if self._search_clause or "SEARCH" not in str(exc).upper():
                    raise
                self._search_clause = False
        return self._run(
            f"CALL db.index.vector.queryNodes('{VECTOR_INDEX}', $k, $vector) YIELD node, score "
            "RETURN node.id AS id, score",
            **params,
        )

    def keyword_search(self, text: str, k: int) -> list[dict[str, Any]]:
        query = lucene_query(text)
        if not query:
            return []
        return self._run(
            f"CALL db.index.fulltext.queryNodes('{TEXT_INDEX}', $query, {{limit: $k}}) "
            "YIELD node, score RETURN node.id AS id, score",
            query=query, k=k,
        )

    def chunks(self, ids: Sequence[str]) -> dict[str, dict[str, Any]]:
        rows = self._run(
            "MATCH (c:HandbookChunk)-[:CHUNK_OF]->(p:HandbookPassage) WHERE c.id IN $ids "
            "RETURN c {.id, .text, .embed_text, .section_number, .heading_path, .line_start, "
            ".line_end, .page_start, .page_end} AS chunk, "
            "p {.id, .title, .text, .section_number, .heading_path, .line_start, .line_end, "
            ".page_start, .page_end, .part, .parts} AS passage",
            ids=list(ids),
        )
        return {r["chunk"]["id"]: r for r in rows}
