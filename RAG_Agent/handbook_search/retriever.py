"""Hybrid handbook retrieval: BM25 + vector search, RRF fusion, cross-encoder rerank.

1. The query is matched against child chunks twice: the Neo4j vector index
   (OpenAI embedding of the query) and the full-text index (Lucene BM25).
2. The two ranked lists are fused with Reciprocal Rank Fusion
   (score = sum of 1 / (60 + rank)), which needs no score calibration.
3. The best ``rerank_pool`` children are re-scored by a local cross-encoder
   (BAAI/bge-reranker-base) reading the query and the chunk together.
4. Children are grouped under their parent passage (a passage scores as its
   best child) and the top passages are returned with citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from .chunking import citation

RRF_K = 60
DEFAULT_RERANKER = "BAAI/bge-reranker-base"


class Reranker(Protocol):
    name: str

    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class CrossEncoderReranker:
    """Local cross-encoder via sentence-transformers (model downloaded once from Hugging Face)."""

    def __init__(self, model: str = DEFAULT_RERANKER, max_length: int = 512) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "Reranking needs sentence-transformers: run with `uv run --extra rerank ...` "
                "or pass --no-rerank"
            ) from exc
        self.name = model
        self.model = CrossEncoder(model, max_length=max_length)

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        return [float(s) for s in self.model.predict([(query, t) for t in texts])]


@dataclass
class Hit:
    passage_id: str
    section_number: str
    title: str
    citation: str
    text: str                       # the parent passage: what a reader / LLM gets
    matched_chunk: str              # the child that matched best
    score: float
    signals: dict[str, Any] = field(default_factory=dict)


def reciprocal_rank_fusion(*rankings: Sequence[str], k: int = RRF_K) -> dict[str, float]:
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + rank)
    return fused


class HybridRetriever:
    def __init__(self, store, embedder, reranker: Reranker | None = None,
                 candidates: int = 30, rerank_pool: int = 20) -> None:
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.candidates = candidates
        self.rerank_pool = rerank_pool

    def search(self, query: str, k: int = 5) -> list[Hit]:
        query = query.strip()
        if not query:
            return []
        vector_hits = self.store.vector_search(self.embedder.embed([query])[0], self.candidates)
        keyword_hits = self.store.keyword_search(query, self.candidates)
        vector_rank = {h["id"]: i for i, h in enumerate(vector_hits, start=1)}
        keyword_rank = {h["id"]: i for i, h in enumerate(keyword_hits, start=1)}
        fused = reciprocal_rank_fusion([h["id"] for h in vector_hits], [h["id"] for h in keyword_hits])
        pool = sorted(fused, key=fused.get, reverse=True)[: self.rerank_pool]
        details = self.store.chunks(pool)
        pool = [cid for cid in pool if cid in details]

        if self.reranker and pool:
            scores = self.reranker.score(query, [details[c]["chunk"]["embed_text"] for c in pool])
            final = dict(zip(pool, scores))
        else:
            final = {cid: fused[cid] for cid in pool}

        best: dict[str, str] = {}             # passage id -> best child id
        for cid in sorted(pool, key=final.get, reverse=True):
            best.setdefault(details[cid]["passage"]["id"], cid)
        hits = []
        for passage_id, cid in list(best.items())[:k]:
            passage = details[cid]["passage"]
            title = passage["title"] + (f" (part {passage['part']}/{passage['parts']})"
                                        if (passage.get("parts") or 1) > 1 else "")
            hits.append(Hit(
                passage_id=passage_id,
                section_number=passage["section_number"],
                title=title,
                citation=citation(passage),
                text=passage["text"],
                matched_chunk=details[cid]["chunk"]["text"],
                score=round(final[cid], 4),
                signals={
                    "vector_rank": vector_rank.get(cid),
                    "bm25_rank": keyword_rank.get(cid),
                    "rrf": round(fused[cid], 5),
                    "reranker": self.reranker.name if self.reranker else None,
                },
            ))
        return hits
