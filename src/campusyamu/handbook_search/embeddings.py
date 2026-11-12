"""OpenAI embeddings for handbook chunks, cached by content hash.

    uv run python -m campusyamu.handbook_search.embeddings

Embeds every child chunk's ``embed_text`` with ``text-embedding-3-small``
(1536 dimensions) and stores the vectors in ``generated/handbook_embeddings.json``
keyed by sha256(model + text), so re-running only pays for new or changed
chunks. Vectors are stored as base64 float32 to keep the file small.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from array import array
from pathlib import Path
from typing import Protocol, Sequence

from ..knowledge_graph.handbook_prose import PROJECT_ROOT, _load_env
from .chunking import DEFAULT_CHUNKS, load_chunks

DEFAULT_MODEL = "text-embedding-3-small"
DIMENSIONS = 1536
DEFAULT_CACHE = Path("data/processed/knowledge_graph/handbook_embeddings.json")
BATCH = 96
MAX_INPUT_CHARS = 24_000          # far below the 8191-token limit; chunks are ~200 words


class Embedder(Protocol):
    model: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """Minimal embeddings client (stdlib only)."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None, timeout: int = 60) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set OPENAI_API_KEY (environment or .env) to create embeddings")
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": [t[:MAX_INPUT_CHARS] for t in texts]}
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": "CampusYamu-HandbookSearch/0.1"},
            method="POST",
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in {429, 500, 502, 503} and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(
                    f"OpenAI HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"
                ) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc
        data = sorted(body["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]


def cache_key(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def encode(vector: Sequence[float]) -> str:
    return base64.b64encode(array("f", vector).tobytes()).decode("ascii")


def decode(value: str) -> list[float]:
    values = array("f")
    values.frombytes(base64.b64decode(value))
    return values.tolist()


def load_cache(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"vectors": {}}


def embed_chunks(chunks: dict, embedder: Embedder, cache_path: Path,
                 dry_run: bool = False) -> dict[str, int]:
    """Embed children missing from the cache; returns counts."""

    cache = load_cache(cache_path)
    vectors: dict[str, str] = cache.setdefault("vectors", {})
    texts = {c["embed_text"] for c in chunks["children"]}
    missing = sorted(t for t in texts if cache_key(embedder.model, t) not in vectors)
    counts = {"children": len(chunks["children"]), "cached": len(texts) - len(missing),
              "to_embed": len(missing), "approx_tokens": sum(len(t) for t in missing) // 4}
    if dry_run or not missing:
        return counts
    for start in range(0, len(missing), BATCH):
        batch = missing[start:start + BATCH]
        for text, vector in zip(batch, embedder.embed(batch)):
            vectors[cache_key(embedder.model, text)] = encode(vector)
        cache["model"] = embedder.model
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")   # save after each batch
        print(f"  embedded {min(start + BATCH, len(missing))}/{len(missing)}")
    return counts


def vector_for(cache: dict, model: str, text: str) -> list[float] | None:
    value = cache.get("vectors", {}).get(cache_key(model, text))
    return decode(value) if value else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed handbook chunks with OpenAI (paid, cached).")
    parser.add_argument("--chunks", type=Path, default=PROJECT_ROOT / DEFAULT_CHUNKS)
    parser.add_argument("--cache", type=Path, default=PROJECT_ROOT / DEFAULT_CACHE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be embedded")
    args = parser.parse_args(argv)
    _load_env(args.env_file)
    chunks = load_chunks(args.chunks)
    if args.dry_run:
        class _Counter:
            model = args.model
        counts = embed_chunks(chunks, _Counter(), args.cache, dry_run=True)  # type: ignore[arg-type]
    else:
        counts = embed_chunks(chunks, OpenAIEmbedder(args.model), args.cache)
    print(f"{counts['children']} chunks: {counts['cached']} already cached, "
          f"{counts['to_embed']} {'to embed' if args.dry_run else 'embedded'} "
          f"(~{counts['approx_tokens']:,} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
