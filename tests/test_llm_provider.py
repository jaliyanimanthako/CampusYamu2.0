"""llm.provider switch: Responses <-> Gemini / Chat Completions translation, keys, models, both embedding sets (no network)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from campusyamu.core import llm, settings
from campusyamu.handbook_search import embeddings
from campusyamu.handbook_search.retriever import HybridRetriever
from campusyamu.handbook_search.store import HandbookStore


def with_settings(values: dict):
    """Patch settings.get with a flat {dotted.key: value} map."""

    return mock.patch.object(settings, "get", lambda key, default=None: values.get(key, default))


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer"],
          "properties": {"answer": {"type": "string"}}}
PAYLOAD = {
    "model": "gemini-test", "store": False, "max_output_tokens": 500,
    "input": [{"role": "system", "content": "Be brief."},
              {"role": "developer", "content": [{"type": "input_text", "text": "JSON only."}]},
              {"role": "user", "content": "first"},
              {"role": "assistant", "content": "earlier answer"},
              {"role": "user", "content": "second"}],
    "text": {"format": {"type": "json_schema", "name": "x", "strict": True, "schema": SCHEMA}},
}


class ProviderAndModelTests(unittest.TestCase):
    def test_provider_key_and_models(self) -> None:
        values = {"llm.provider": "Gemini", "models.gemini.chat": "g-chat", "models.openai.chat": "o-chat",
                  "models.guardrail": "gemini-decision-1"}
        with with_settings(values), mock.patch.dict(os.environ, {"GEMINI_API_KEY": "g", "OPENAI_API_KEY": ""}):
            self.assertEqual(llm.provider(), "gemini")
            self.assertEqual(llm.key_name(), "GEMINI_API_KEY")
            self.assertTrue(llm.available())
            self.assertFalse(llm.available("openai"))
            self.assertEqual(settings.model("chat"), "g-chat")
            self.assertEqual(settings.model("chat", provider="openai"), "o-chat")
            self.assertEqual(settings.model("guardrail"), "gemini-decision-1")     # one-service role
            self.assertEqual(settings.model("memory"), llm.DEFAULT_MODELS["gemini"])
        with with_settings({}):
            self.assertEqual(llm.provider(), "openai")                            # built-in default
        with with_settings({"llm.provider": "claude"}), self.assertRaises(ValueError):
            llm.provider()

    def test_missing_key_names_the_provider_key(self) -> None:
        with with_settings({"llm.provider": "gemini"}), mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                llm.require_key()


class GeminiTranslationTests(unittest.TestCase):
    def test_structured_request(self) -> None:
        with with_settings({"llm.gemini.thinking": "low", "llm.gemini.extra_output_tokens": 1000}):
            body = llm.gemini_request(PAYLOAD)
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "Be brief.\n\nJSON only.")
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        self.assertEqual(body["contents"][1]["parts"], [{"text": "earlier answer"}])
        config = body["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["responseJsonSchema"], SCHEMA)
        self.assertEqual(config["maxOutputTokens"], 1500)
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "low"})
        with with_settings({"llm.gemini.thinking": 0}):
            self.assertEqual(llm.gemini_request(PAYLOAD)["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})
        with with_settings({"llm.gemini.thinking": ""}):
            self.assertNotIn("thinkingConfig", llm.gemini_request(PAYLOAD)["generationConfig"])

    def test_reply_text_skips_thoughts_and_parses(self) -> None:
        reply = {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
            {"text": "thinking...", "thought": True}, {"text": '{"answer": '}, {"text": '"ok"}'}]}}]}
        self.assertEqual(llm.structured_output(llm.gemini_to_responses(reply)), {"answer": "ok"})

    def test_max_tokens_and_blocks_raise(self) -> None:
        cut = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": '{"ans'}]}}]}
        with self.assertRaisesRegex(RuntimeError, "did not complete"):
            llm.response_text(llm.gemini_to_responses(cut))
        blocked = {"promptFeedback": {"blockReason": "SAFETY"}}
        with self.assertRaisesRegex(RuntimeError, "refused"):
            llm.response_text(llm.gemini_to_responses(blocked))

    def test_tool_call_round_trip_keeps_signature_and_name(self) -> None:
        reply = {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
            {"text": "Searching."},
            {"functionCall": {"name": "web_search", "args": {"query": "QS jobs"}, "id": "g1"},
             "thoughtSignature": "SIG"},
            {"functionCall": {"name": "web_search", "args": {"query": "QS pay"}}}]}}]}
        turn = llm.gemini_to_responses(reply)
        calls = [i for i in turn["output"] if i["type"] == "function_call"]
        self.assertEqual([json.loads(c["arguments"]) for c in calls], [{"query": "QS jobs"}, {"query": "QS pay"}])
        self.assertEqual(turn["output"][0]["content"][0]["text"], "Searching.")

        tools = [{"type": "function", "name": "web_search", "description": "Search", "strict": True,
                  "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}}]
        follow_up = {"model": "m", "instructions": "Research.", "tools": tools, "input": [
            {"role": "user", "content": "task"}, {"role": "assistant", "content": "Searching."}, *calls,
            {"type": "function_call_output", "call_id": calls[0]["call_id"], "output": '{"results": []}'},
            {"type": "function_call_output", "call_id": calls[1]["call_id"], "output": "plain text"}]}
        with with_settings({}):
            body = llm.gemini_request(follow_up)
        self.assertEqual([c["role"] for c in body["contents"]], ["user", "model", "user"])
        model_parts = body["contents"][1]["parts"]
        self.assertEqual(model_parts[0], {"text": "Searching."})
        self.assertEqual(model_parts[1]["functionCall"], {"name": "web_search", "args": {"query": "QS jobs"}, "id": "g1"})
        self.assertEqual(model_parts[1]["thoughtSignature"], "SIG")
        self.assertNotIn("thoughtSignature", model_parts[2])
        responses = [p["functionResponse"] for p in body["contents"][2]["parts"]]
        self.assertEqual(responses[0], {"name": "web_search", "response": {"results": []}, "id": "g1"})
        self.assertEqual(responses[1], {"name": "web_search", "response": {"result": "plain text"}})
        declaration = body["tools"][0]["functionDeclarations"][0]
        self.assertEqual(declaration["parametersJsonSchema"], tools[0]["parameters"])

    def test_call_structured_routes_by_provider(self) -> None:
        sent = []

        def fake_post(url, payload, auth, timeout, user_agent, who, attempts=3):
            sent.append((url, payload, auth))
            if "generateContent" in url:
                return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"answer": "g"}'}]}}]}
            return {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": '{"answer": "o"}'}]}]}

        with mock.patch.object(llm, "post_json", fake_post):
            with with_settings({"llm.provider": "gemini"}):
                self.assertEqual(llm.call_structured(PAYLOAD, "gk"), {"answer": "g"})
            with with_settings({"llm.provider": "openai"}):
                self.assertEqual(llm.call_structured(PAYLOAD, "ok"), {"answer": "o"})
        self.assertTrue(sent[0][0].endswith("/models/gemini-test:generateContent"))
        self.assertEqual(sent[0][2], {"x-goog-api-key": "gk"})
        self.assertTrue(sent[1][0].endswith("/v1/responses"))
        self.assertEqual(sent[1][1], PAYLOAD)                                  # OpenAI gets it untouched
        self.assertEqual(sent[1][2], {"Authorization": "Bearer ok"})

    def test_chat_completions_uses_gemini_openai_endpoint(self) -> None:
        sent = []
        with mock.patch.object(llm, "post_json", lambda url, *a, **k: sent.append(url) or {}):
            with with_settings({"llm.provider": "gemini"}):
                llm.chat_completions({"model": "m", "messages": []}, api_key="k")
        self.assertTrue(sent[0].endswith("/v1beta/openai/chat/completions"))


class OpenRouterTests(unittest.TestCase):
    def test_structured_request_and_routing(self) -> None:
        sent = []

        def fake_post(url, payload, auth, timeout, user_agent, who, attempts=4):
            sent.append((url, payload, auth, who))
            return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant",
                                                                      "content": '{"answer": "r"}'}}]}

        values = {"llm.provider": "openrouter", "llm.openrouter.reasoning": "low",
                  "llm.openrouter.extra_output_tokens": 100}
        with with_settings(values), mock.patch.object(llm, "post_json", fake_post):
            self.assertEqual(llm.call_structured(PAYLOAD, "rk"), {"answer": "r"})
        url, body, auth, who = sent[0]
        self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(auth, {"Authorization": "Bearer rk"})
        self.assertEqual(who, "OpenRouter")
        self.assertEqual(body["model"], "gemini-test")
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "system", "user", "assistant", "user"])
        self.assertEqual(body["messages"][1]["content"], "JSON only.")
        self.assertEqual(body["response_format"], {"type": "json_schema", "json_schema": {
            "name": "x", "strict": True, "schema": SCHEMA}})
        self.assertEqual(body["max_tokens"], 600)
        self.assertEqual(body["reasoning"], {"effort": "low"})
        self.assertEqual(body["provider"], {"require_parameters": True})

    def test_tool_call_round_trip(self) -> None:
        tools = [{"type": "function", "name": "get_time", "description": "d", "strict": True,
                  "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}]
        reply = llm.chat_to_responses({"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "get_time", "arguments": '{"city": "Kandy"}'}},
                {"id": "c2", "type": "function", "function": {"name": "get_time", "arguments": '{"city": "Galle"}'}}]}}]})
        calls = [i for i in reply["output"] if i["type"] == "function_call"]
        self.assertEqual([c["call_id"] for c in calls], ["c1", "c2"])
        with with_settings({}):
            body = llm.chat_request({"model": "m", "tools": tools, "input": [
                {"role": "user", "content": "time?"}, *calls,
                {"type": "function_call_output", "call_id": "c1", "output": '{"time": "10:30"}'},
                {"type": "function_call_output", "call_id": "c2", "output": {"time": "10:31"}}]})
        user, assistant, tool1, tool2 = body["messages"]
        self.assertEqual([c["id"] for c in assistant["tool_calls"]], ["c1", "c2"])   # one assistant turn
        self.assertEqual(tool1, {"role": "tool", "tool_call_id": "c1", "content": '{"time": "10:30"}'})
        self.assertEqual(json.loads(tool2["content"]), {"time": "10:31"})
        self.assertEqual(body["tools"][0]["function"]["name"], "get_time")
        self.assertTrue(body["tools"][0]["function"]["strict"])
        self.assertNotIn("reasoning", body)

    def test_length_refusal_and_errors(self) -> None:
        cut = llm.chat_to_responses({"choices": [{"finish_reason": "length", "message": {"content": '{"a'}}]})
        with self.assertRaisesRegex(RuntimeError, "did not complete"):
            llm.response_text(cut)
        refused = llm.chat_to_responses({"choices": [{"finish_reason": "stop", "message": {"refusal": "no"}}]})
        with self.assertRaisesRegex(RuntimeError, "refused"):
            llm.response_text(refused)
        with self.assertRaisesRegex(RuntimeError, "OpenRouter error: no credit"):
            llm.chat_to_responses({"error": {"message": "no credit", "code": 402}})

    def test_chat_completions_and_embeddings_endpoints(self) -> None:
        sent = []

        def fake_post(url, payload, auth, timeout, user_agent, who, attempts=4):
            sent.append((url, payload))
            return {"data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]}

        with mock.patch.object(llm, "post_json", fake_post), with_settings({"llm.provider": "openrouter"}), \
                mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "rk"}):
            llm.chat_completions({"model": "m", "messages": []})
            embedder = embeddings.make_embedder()
            self.assertIsInstance(embedder, embeddings.OpenRouterEmbedder)
            self.assertEqual(embedder.cache_id, "openai/text-embedding-3-small")
            self.assertEqual(embedder.embed(["a", "b"]), [[0.1], [0.2]])
        self.assertEqual(sent[0][0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(sent[1][0], "https://openrouter.ai/api/v1/embeddings")
        self.assertEqual(sent[1][1]["model"], "openai/text-embedding-3-small")


class FakeDriver:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict]] = []

    def execute_query(self, cypher, params, database_=None):
        self.queries.append((cypher, params))
        if "RETURN passages" in cypher:
            return [{"passages": 1, "chunks": 2, "linked_to_kg": 0}], None, None
        return [], None, None


class EmbeddingSetsTests(unittest.TestCase):
    CHUNKS = {"parents": [{"id": "p1", "line_start": 1}],
              "children": [{"id": "c1", "parent_id": "p1", "embed_text": "aa"},
                           {"id": "c2", "parent_id": "p1", "embed_text": "bb"}]}

    def test_cache_ids_keep_both_sets_apart(self) -> None:
        with with_settings({"llm.gemini.embedding_dimensions": 768}):
            self.assertEqual(embeddings.cache_id("gemini"), "gemini-embedding-001@768")
            self.assertEqual(embeddings.cache_id("openai"), "text-embedding-3-small")

    def test_gemini_embedder_request(self) -> None:
        sent = []

        def fake_post(url, payload, auth, *a, **k):
            sent.append((url, payload, auth))
            return {"embeddings": [{"values": [0.1, 0.2]} for _ in payload["requests"]]}

        with with_settings({"llm.gemini.embedding_dimensions": 2}), mock.patch.object(llm, "post_json", fake_post):
            doc = embeddings.GeminiEmbedder(api_key="k")
            query = embeddings.GeminiEmbedder(api_key="k", query=True)
            self.assertEqual(doc.embed(["a", "b"]), [[0.1, 0.2], [0.1, 0.2]])
            query.embed(["q"])
        url, payload, auth = sent[0]
        self.assertTrue(url.endswith("/models/gemini-embedding-001:batchEmbedContents"))
        self.assertEqual(auth, {"x-goog-api-key": "k"})
        self.assertEqual(payload["requests"][0]["taskType"], "RETRIEVAL_DOCUMENT")
        self.assertEqual(payload["requests"][0]["outputDimensionality"], 2)
        self.assertEqual(sent[1][1]["requests"][0]["taskType"], "RETRIEVAL_QUERY")
        self.assertEqual(doc.cache_id, "gemini-embedding-001@2")

    def test_both_sets_in_one_cache_and_both_loaded(self) -> None:
        class Fake:
            def __init__(self, cache_id, value):
                self.model = self.cache_id = cache_id
                self.value = value

            def embed(self, texts):
                return [[self.value, 1.0, 0.0] for _ in texts]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.json"
            embeddings.embed_chunks(self.CHUNKS, Fake("text-embedding-3-small", 1.0), path)
            embeddings.embed_chunks(self.CHUNKS, Fake("gemini-embedding-001@3", 2.0), path)
            again = embeddings.embed_chunks(self.CHUNKS, Fake("gemini-embedding-001@3", 9.0), path)
            cache = embeddings.load_cache(path)
        self.assertEqual(again["to_embed"], 0)                                 # cached: nothing paid twice
        self.assertEqual(cache["models"], ["gemini-embedding-001@3", "text-embedding-3-small"])
        self.assertEqual(len(cache["vectors"]), 4)

        driver = FakeDriver()
        counts = HandbookStore(driver, provider="gemini").load(
            self.CHUNKS, cache, {"openai": "text-embedding-3-small", "gemini": "gemini-embedding-001@3"})
        self.assertEqual(counts["dimensions"], {"openai": 3, "gemini": 3})
        rows = next(p["rows"] for q, p in driver.queries if "HandbookChunk" in q and "rows" in p)
        self.assertEqual(rows[0]["embedding_openai"][0], 1.0)
        self.assertEqual(rows[0]["embedding_gemini"][0], 2.0)
        created = [q for q, _ in driver.queries if q.startswith("CREATE VECTOR INDEX")]
        self.assertEqual(len(created), 2)
        self.assertIn("ON c.embedding_gemini", created[1])

        partial = {"vectors": {embeddings.cache_key("text-embedding-3-small", "aa"): embeddings.encode([1.0])}}
        with self.assertRaisesRegex(SystemExit, "No complete embedding set"):
            HandbookStore(FakeDriver(), provider="openai").load(self.CHUNKS, partial,
                                                                 {"openai": "text-embedding-3-small"})

    def test_search_uses_the_configured_provider_index(self) -> None:
        driver = FakeDriver()
        HandbookStore(driver, provider="gemini").vector_search([0.1], 3)
        self.assertIn("handbook_chunk_embedding_gemini", driver.queries[0][0])


class KeywordFallbackTests(unittest.TestCase):
    class Store:
        def vector_search(self, vector, k):
            raise RuntimeError("no such index")

        def keyword_search(self, text, k):
            return [{"id": "c1", "score": 1.0}]

        def chunks(self, ids):
            chunk = {"id": "c1", "text": "t", "embed_text": "t", "section_number": "1", "heading_path": ["H"],
                     "line_start": 1, "line_end": 2, "page_start": 1, "page_end": 1}
            passage = {**chunk, "id": "p1", "title": "Z-score", "part": 1, "parts": 1}
            return {"c1": {"chunk": chunk, "passage": passage}}

    class Embedder:
        model = "m"

        def embed(self, texts):
            return [[0.1] for _ in texts]

    def test_bm25_only_when_vectors_fail_or_no_embedder(self) -> None:
        for embedder in (self.Embedder(), None):
            retriever = HybridRetriever(self.Store(), embedder, None)
            hits = retriever.search("z score", k=1)
            self.assertEqual([h.passage_id for h in hits], ["p1"])
            self.assertTrue(retriever.vector_error)


if __name__ == "__main__":
    unittest.main()
