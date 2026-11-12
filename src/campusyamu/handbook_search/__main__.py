"""Handbook vector search: chunk -> embed -> load -> search.

    uv run python -m campusyamu.handbook_search chunk
    uv run python -m campusyamu.handbook_search embed          # OpenAI, paid (cents)
    uv run python -m campusyamu.handbook_search load           # into Neo4j
    uv run --extra rerank python -m campusyamu.handbook_search search "your question"

Neo4j and OpenAI settings come from .env (NEO4J_URI, NEO4J_USER,
NEO4J_PASSWORD, NEO4J_DATABASE, OPENAI_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import textwrap
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from ..knowledge_graph.handbook_prose import PROJECT_ROOT, _load_env
from . import chunking, embeddings
from .retriever import DEFAULT_RERANKER, CrossEncoderReranker, HybridRetriever
from .store import HandbookStore, connect


def _print_hits(hits, full: bool) -> None:
    if not hits:
        print("No passages found.")
    for rank, hit in enumerate(hits, start=1):
        s = hit.signals
        print(f"\n[{rank}] {hit.title}  —  {hit.citation}")
        print(f"    score {hit.score}  (vector #{s['vector_rank'] or '-'}, BM25 #{s['bm25_rank'] or '-'}, "
              f"RRF {s['rrf']})")
        body = hit.text if full else hit.matched_chunk
        print(textwrap.indent(textwrap.shorten(body, 700, placeholder=" …") if not full else body, "    "))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handbook_search", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--chunks", type=Path, default=PROJECT_ROOT / chunking.DEFAULT_CHUNKS)
    parser.add_argument("--cache", type=Path, default=PROJECT_ROOT / embeddings.DEFAULT_CACHE)
    parser.add_argument("--model", default=embeddings.DEFAULT_MODEL, help="Embedding model")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("chunk", help="Split the handbook into parent/child chunks (free)")
    embed = sub.add_parser("embed", help="Embed chunks with OpenAI (paid, cached)")
    embed.add_argument("--dry-run", action="store_true")
    sub.add_parser("load", help="Load passages, chunks and indexes into Neo4j")
    search = sub.add_parser("search", help="Hybrid search with reranking")
    search.add_argument("query")
    search.add_argument("-k", type=int, default=5, help="Passages to return")
    search.add_argument("--candidates", type=int, default=30, help="Hits taken from each index")
    search.add_argument("--no-rerank", action="store_true", help="Rank by RRF only")
    search.add_argument("--reranker", default=DEFAULT_RERANKER)
    search.add_argument("--full", action="store_true", help="Print whole parent passages")
    search.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    _load_env(args.env_file)

    if args.command == "chunk":
        return chunking.main(["--output", str(args.chunks)])
    if args.command == "embed":
        return embeddings.main(["--chunks", str(args.chunks), "--cache", str(args.cache),
                                "--model", args.model] + (["--dry-run"] if args.dry_run else []))

    with connect() as driver:
        store = HandbookStore(driver)
        if args.command == "load":
            counts = store.load(chunking.load_chunks(args.chunks),
                                embeddings.load_cache(args.cache), args.model)
            print(f"Loaded {counts['passages']} passages and {counts['chunks']} chunks "
                  f"({counts['dimensions']}-d vectors); {counts['linked_to_kg']} passages linked "
                  "to KG HandbookSection nodes")
            return 0
        reranker = None if args.no_rerank else CrossEncoderReranker(args.reranker)
        retriever = HybridRetriever(store, embeddings.OpenAIEmbedder(args.model), reranker,
                                    candidates=args.candidates)
        hits = retriever.search(args.query, args.k)
    if args.json:
        print(json.dumps([asdict(h) for h in hits], ensure_ascii=False, indent=2))
    else:
        _print_hits(hits, args.full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
