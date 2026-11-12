from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from RAG_Agent.handbook_search import chunking, embeddings
from RAG_Agent.handbook_search.retriever import HybridRetriever, reciprocal_rank_fusion
from RAG_Agent.handbook_search.store import lucene_query
from RAG_Agent.graph_pipeline.source_registry import PROJECT_ROOT


class ChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.markdown = (PROJECT_ROOT / chunking.HANDBOOK).read_text(encoding="utf-8")
        cls.parents, cls.children = chunking.build_chunks(cls.markdown)

    def test_sections_follow_numbering_not_heading_levels(self) -> None:
        sections = {p.section_number for p in self.parents}
        for expected in ("1.2", "1.7", "2.2.1.1", "2.2.3.1", "Annex (a)"):
            self.assertIn(expected, sections)
        self.assertFalse(any(s.startswith("Basket") for s in sections))    # sub-headings
        self.assertNotIn("Contents", sections)
        basket = next(c for c in self.children if "Guidance for selection of subjects from basket 03"
                      in c.embed_text)
        self.assertEqual(basket.section_number, "2.2.1.1")

    def test_every_content_line_lands_in_one_child(self) -> None:
        covered = set()
        for child in self.children:
            covered.update(range(child.line_start, child.line_end + 1))
        lines = self.markdown.splitlines()
        start = lines.index("## Contents") + 1
        end = next(i for i in range(start, len(lines)) if lines[i].startswith("## "))
        for number, line in enumerate(lines, start=1):
            text = line.strip()
            if (not text or text.startswith(("#", "<!--")) or start < number <= end):
                continue
            self.assertIn(number, covered, f"line {number} not chunked: {text[:60]}")

    def test_sizes_and_parent_links(self) -> None:
        parent_ids = {p.id for p in self.parents}
        self.assertEqual(len(parent_ids), len(self.parents))
        for child in self.children:
            self.assertIn(child.parent_id, parent_ids)
            self.assertLessEqual(len(child.text.split()), chunking.CHILD_MAX_WORDS * 2)
        for parent in self.parents:
            self.assertLessEqual(len(parent.text.split()),
                                 chunking.PARENT_MAX_WORDS + chunking.PARENT_MIN_TAIL_WORDS)

    def test_citation_has_section_pages_and_lines(self) -> None:
        medicine = next(p for p in self.parents if p.section_number == "2.2.3.1")
        self.assertRegex(chunking.citation(medicine), r"^Handbook §2\.2\.3\.1, p\. 58, lines \d+–\d+$")
        self.assertIn("Medicine", medicine.text + medicine.title)


class FakeEmbedder:
    model = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        return [[float(len(t)), 1.0, 0.5] for t in texts]


class EmbeddingCacheTests(unittest.TestCase):
    def test_cache_only_embeds_new_text(self) -> None:
        chunks = {"children": [{"embed_text": "a"}, {"embed_text": "bb"}, {"embed_text": "a"}]}
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            embedder = FakeEmbedder()
            first = embeddings.embed_chunks(chunks, embedder, cache_path)
            second = embeddings.embed_chunks(chunks, embedder, cache_path)
            self.assertEqual((first["to_embed"], second["to_embed"], embedder.calls), (2, 0, 1))
            cache = embeddings.load_cache(cache_path)
            self.assertEqual(embeddings.vector_for(cache, "fake", "bb"), [2.0, 1.0, 0.5])
            self.assertIsNone(embeddings.vector_for(cache, "other-model", "bb"))


class FakeStore:
    """Two indexes over four chunks in three passages."""

    CHUNKS = {
        "c1": ("p1", "Common General Paper 30% minimum"),
        "c2": ("p1", "S grades in three subjects"),
        "c3": ("p2", "Z score calculation"),
        "c4": ("p3", "district of a candidate"),
    }

    def vector_search(self, vector, k):
        return [{"id": "c3"}, {"id": "c2"}, {"id": "c4"}][:k]

    def keyword_search(self, text, k):
        return [{"id": "c1"}, {"id": "c3"}][:k]

    def chunks(self, ids):
        out = {}
        for cid in ids:
            pid, text = self.CHUNKS[cid]
            out[cid] = {
                "chunk": {"id": cid, "text": text, "embed_text": text},
                "passage": {"id": pid, "title": pid, "text": f"passage {pid}", "section_number": "1.2",
                            "line_start": 1, "line_end": 2, "page_start": 16, "page_end": 16,
                            "part": 1, "parts": 1},
            }
        return out


class KeywordReranker:
    name = "keyword"

    def score(self, query, texts):
        words = set(query.lower().split())
        return [len(words & set(t.lower().split())) for t in texts]


class RetrieverTests(unittest.TestCase):
    def test_rrf_rewards_agreement(self) -> None:
        fused = reciprocal_rank_fusion(["a", "b"], ["b", "c"])
        self.assertEqual(max(fused, key=fused.get), "b")

    def test_lucene_query_drops_syntax(self) -> None:
        self.assertEqual(lucene_query('Z-score "cut-off" (2024)? AND/OR'),
                         "z OR score OR cut OR off OR 2024 OR and OR or")

    def test_rerank_then_group_by_passage(self) -> None:
        retriever = HybridRetriever(FakeStore(), FakeEmbedder(), KeywordReranker())
        hits = retriever.search("minimum common general paper", k=3)
        self.assertEqual([h.passage_id for h in hits][:1], ["p1"])
        self.assertEqual(hits[0].matched_chunk, "Common General Paper 30% minimum")
        self.assertEqual(len({h.passage_id for h in hits}), len(hits))     # one hit per passage
        self.assertEqual(hits[0].signals["bm25_rank"], 1)

    def test_without_reranker_uses_rrf(self) -> None:
        hits = HybridRetriever(FakeStore(), FakeEmbedder(), None).search("z score", k=2)
        self.assertEqual(hits[0].passage_id, "p2")        # c3 is in both lists


if __name__ == "__main__":
    unittest.main()
