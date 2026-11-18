"""Handbook chunk embeddings (OpenAI, Gemini, OpenRouter or Groq), cached by content hash.

    uv run python -m campusyamu.handbook_search.embeddings                  # the llm.embedding_provider set
    uv run python -m campusyamu.handbook_search.embeddings --provider all   # every set with a key

Embeds every child chunk's ``embed_text`` and stores the vectors in
``data/processed/knowledge_graph/handbook_embeddings.json`` keyed by
sha256(cache id + text). Every provider's vectors live side by side in that file
(cache ids ``text-embedding-3-small``, ``gemini-embedding-001@1536`` and
``openai/text-embedding-3-small`` for OpenRouter), so
re-running only pays for new or changed chunks and switching provider never
re-embeds. Vectors are stored as base64 float32 to keep the file small.

Models: models.<provider>.embedding in settings.yaml;
Gemini's vector size: llm.gemini.embedding_dimensions.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from array import array
from pathlib import Path
from typing import Protocol, Sequence

from ..core import llm, settings
from ..knowledge_graph.handbook_prose import PROJECT_ROOT, _load_env
from .chunking import DEFAULT_CHUNKS, load_chunks

DEFAULT_MODELS = {"openai": "text-embedding-3-small", "gemini": "gemini-embedding-001",
                  "openrouter": "openai/text-embedding-3-small"}
DEFAULT_MODEL = DEFAULT_MODELS["openai"]
DIMENSIONS = 1536
DEFAULT_CACHE = Path("data/processed/knowledge_graph/handbook_embeddings.json")
BATCH = 96
MAX_INPUT_CHARS = 24_000          # far below the 8191-token limit; chunks are ~200 words
MAX_GEMINI_CHARS = 7_000          # gemini-embedding-001 reads 2048 tokens


class Embedder(Protocol):
    model: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def embedding_model(provider: str) -> str:
    return settings.model("embedding", DEFAULT_MODELS[provider], provider=provider)


def gemini_dimensions() -> int | None:
    value = settings.get("llm.gemini.embedding_dimensions", DIMENSIONS)
    return int(value) if value else None


def cache_id(provider: str, model: str | None = None) -> str:
    """The cache key prefix (and identity) of one provider's vectors; needs no API key."""

    model = model or embedding_model(provider)
    dims = gemini_dimensions() if provider == "gemini" else None
    return f"{model}@{dims}" if dims else model


class OpenAIEmbedder:
    """Minimal OpenAI-format /embeddings client (stdlib only)."""

    provider = "openai"
    url = llm.OPENAI_URL

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: int = 60) -> None:
        self.model = model or embedding_model(self.provider)
        self.cache_id = cache_id(self.provider, self.model)
        self.api_key = api_key or llm.api_key(self.provider)
        if not self.api_key:
            raise RuntimeError(f"Set {llm.key_name(self.provider)} (environment or .env) to create "
                               f"{llm.label(self.provider)} embeddings")
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        payload = {"model": self.model, "input": [t[:MAX_INPUT_CHARS] for t in texts]}
        body = llm.post_json(f"{self.url}/embeddings", payload, {"Authorization": f"Bearer {self.api_key}"},
                             self.timeout, "CampusYamu-HandbookSearch/0.1", llm.label(self.provider), attempts=4)
        if not body.get("data"):
            raise RuntimeError(f"{llm.label(self.provider)} returned no embeddings: {str(body)[:300]}")
        data = sorted(enumerate(body["data"]), key=lambda pair: pair[1].get("index", pair[0]))
        return [item["embedding"] for _, item in data]


class OpenRouterEmbedder(OpenAIEmbedder):
    """OpenRouter's /embeddings (same format); models are named vendor/model."""

    provider = "openrouter"
    url = llm.OPENROUTER_URL


class GeminiEmbedder:
    """Gemini batchEmbedContents. Passages and questions are embedded as the two sides of retrieval."""

    provider = "gemini"
    max_batch = 100                       # requests per batchEmbedContents call

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: int = 60,
                 query: bool = False, dimensions: int | None = None) -> None:
        self.model = model or embedding_model("gemini")
        self.dimensions = dimensions if dimensions is not None else gemini_dimensions()
        self.cache_id = f"{self.model}@{self.dimensions}" if self.dimensions else self.model
        self.task = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
        self.api_key = api_key or llm.api_key("gemini")
        if not self.api_key:
            raise RuntimeError("Set GEMINI_API_KEY (environment or .env) to create Gemini embeddings")
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.max_batch):
            requests = [{"model": f"models/{self.model}", "taskType": self.task,
                         "content": {"parts": [{"text": t[:MAX_GEMINI_CHARS]}]},
                         **({"outputDimensionality": self.dimensions} if self.dimensions else {})}
                        for t in texts[start:start + self.max_batch]]
            body = llm.post_json(f"{llm.GEMINI_URL}/models/{self.model}:batchEmbedContents", {"requests": requests},
                                 {"x-goog-api-key": self.api_key}, self.timeout, "CampusYamu-HandbookSearch/0.1",
                                 "Gemini", attempts=4)
            vectors.extend(item["values"] for item in body["embeddings"])
        return vectors


def make_embedder(provider: str | None = None, query: bool = False, model: str | None = None) -> Embedder:
    """The embedder for a provider (default llm.embedding_provider); `query` for search questions."""

    provider = provider or llm.embedding_provider()
    if provider == "gemini":
        return GeminiEmbedder(model, query=query)
    if provider == "openrouter":
        return OpenRouterEmbedder(model)
    return OpenAIEmbedder(model)


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
    key_id = getattr(embedder, "cache_id", embedder.model)
    missing = sorted(t for t in texts if cache_key(key_id, t) not in vectors)
    counts = {"children": len(chunks["children"]), "cached": len(texts) - len(missing),
              "to_embed": len(missing), "approx_tokens": sum(len(t) for t in missing) // 4}
    if dry_run or not missing:
        return counts
    for start in range(0, len(missing), BATCH):
        batch = missing[start:start + BATCH]
        for text, vector in zip(batch, embedder.embed(batch)):
            vectors[cache_key(key_id, text)] = encode(vector)
        legacy = [cache.pop("model")] if "model" in cache else []      # older files named one model
        cache["models"] = sorted({*cache.get("models", []), *legacy, key_id})
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")   # save after each batch
        print(f"  embedded {min(start + BATCH, len(missing))}/{len(missing)}")
    return counts


def vector_for(cache: dict, model: str, text: str) -> list[float] | None:
    value = cache.get("vectors", {}).get(cache_key(model, text))
    return decode(value) if value else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed handbook chunks (paid, cached).")
    parser.add_argument("--chunks", type=Path, default=PROJECT_ROOT / DEFAULT_CHUNKS)
    parser.add_argument("--cache", type=Path, default=PROJECT_ROOT / DEFAULT_CACHE)
    parser.add_argument("--provider", choices=(*llm.EMBEDDING_PROVIDERS, "all"),
                        help="whose embeddings to make (default: llm.embedding_provider in settings.yaml)")
    parser.add_argument("--model", help="override the provider's embedding model (one provider only)")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be embedded")
    args = parser.parse_args(argv)
    _load_env(args.env_file)
    chunks = load_chunks(args.chunks)
    providers = list(llm.EMBEDDING_PROVIDERS) if args.provider == "all" else [args.provider or llm.embedding_provider()]
    if args.provider == "all" and not args.dry_run:
        for provider in [p for p in providers if not llm.available(p)]:
            print(f"{provider}: skipped ({llm.key_name(provider)} not set)")
        providers = [p for p in providers if llm.available(p)]
    for provider in providers:
        model = args.model if len(providers) == 1 else None
        if args.dry_run:
            class _Counter:
                pass
            counter = _Counter()
            counter.model = counter.cache_id = cache_id(provider, model)     # type: ignore[attr-defined]
            counts = embed_chunks(chunks, counter, args.cache, dry_run=True)  # type: ignore[arg-type]
        else:
            counts = embed_chunks(chunks, make_embedder(provider, model=model), args.cache)
        print(f"{provider} ({cache_id(provider, model)}): {counts['children']} chunks: {counts['cached']} "
              f"already cached, {counts['to_embed']} {'to embed' if args.dry_run else 'embedded'} "
              f"(~{counts['approx_tokens']:,} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
