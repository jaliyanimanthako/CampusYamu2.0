"""Streaming chat answers (LangChain): the hidden meta line, citations, provider models, and /v1/chat/stream."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage

from campusyamu.core import chat_stream
from campusyamu.web.career_outlook import CareerOutlookStore
from campusyamu.web.course_chat import CourseChat, MetaSplitter, cited_ids, parse_meta

COURSE = {"course_code": "023", "uni_code": "023G", "course_name": "Architecture",
          "university": "University of Moratuwa", "band": "strong", "latest_cutoff": 0.7878,
          "expected_margin": 0.64, "aptitude_test": True, "details_block": 0}


def fake(text: str) -> GenericFakeChatModel:
    """A LangChain chat model that streams `text` word by word."""

    return GenericFakeChatModel(messages=iter([AIMessage(content=text)]))


class MetaSplitterTests(unittest.TestCase):
    def test_marker_split_across_pieces_is_never_shown(self) -> None:
        sp = MetaSplitter()
        pieces = ["Yes [S1].", "\n<", "<me", 'ta {"status": "answered", ', '"start_career_research": true}>>']
        shown = "".join(sp.feed(p) for p in pieces) + sp.finish()
        self.assertEqual(shown.strip(), "Yes [S1].")
        self.assertNotIn("<<", shown)
        self.assertEqual(parse_meta(sp.meta), {"status": "answered", "start_career_research": True})

    def test_lookalike_text_is_shown(self) -> None:
        sp = MetaSplitter()
        shown = sp.feed("a < b <") + sp.feed("< c") + sp.finish()
        self.assertEqual(shown, "a < b << c")
        self.assertIsNone(sp.meta)

    def test_missing_or_broken_meta(self) -> None:
        self.assertEqual(parse_meta(None), {})
        self.assertEqual(parse_meta("<<meta {not json}>>"), {})

    def test_cited_ids(self) -> None:
        self.assertEqual(cited_ids("A [S1]. B [R, S1] and [H2;W] [X9] [link]", {"S1", "R", "H2", "W"}),
                         ["S1", "R", "H2", "W"])


class CourseChatStreamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chat = CourseChat(use_search=False, model="test-model", outlooks=CareerOutlookStore(Path(self.tmp.name)))

    def ask(self, text: str, question: str = "Is there an aptitude test?"):
        self.chat.stream_model = fake(text)
        tokens: list[str] = []
        result = self.chat.ask(question, COURSE, {"z_score": 1.7}, [], on_token=tokens.append)
        return result, tokens

    def test_answer_streams_and_matches_the_result(self) -> None:
        result, tokens = self.ask('Yes, Moratuwa runs an aptitude test [S1]. Your margin is +0.64 [R].\n'
                                  '<<meta {"status": "answered", "start_career_research": false}>>')
        self.assertGreater(len(tokens), 5)                                  # it arrived in pieces
        self.assertEqual("".join(tokens).strip(), result["answer"])
        self.assertEqual(result["answer"], "Yes, Moratuwa runs an aptitude test [S1]. Your margin is +0.64 [R].")
        self.assertNotIn("meta", "".join(tokens))
        self.assertEqual([s["id"] for s in result["sources"]], ["S1", "R"])  # from the citations
        self.assertEqual(result["status"], "answered")
        self.assertFalse(result["start_career_research"])

    def test_flags_come_from_the_meta_line(self) -> None:
        result, _ = self.ask('Research has started; keep asking.\n'
                             '<<meta {"status": "answered", "start_career_research": true}>>', "yes, research it")
        self.assertTrue(result["start_career_research"])
        result, _ = self.ask("The handbook does not say [S9].")             # no meta, unknown id
        self.assertEqual((result["status"], result["sources"]), ("answered", []))
        result, _ = self.ask('Sorry, I can\'t help with that.\n<<meta {"status": "out_of_scope", '
                             '"start_career_research": true}>>', "write my essay")
        self.assertEqual(result["status"], "out_of_scope")
        self.assertFalse(result["start_career_research"])                   # never for out-of-scope

    def test_stream_uses_the_same_prompt_plus_the_text_format(self) -> None:
        seen = {}

        def capture(messages, on_token, **kwargs):
            seen["messages"] = messages
            on_token('Fine [S1].\n<<meta {"status": "answered", "start_career_research": false}>>')
            return ""
        with mock.patch.object(chat_stream, "stream_text", capture):
            result = self.chat.ask("q", COURSE, {}, [], on_token=lambda t: None)
        systems = [m["content"] for m in seen["messages"] if m["role"] == "system"]
        self.assertIn("Context:", systems[1])
        self.assertIn("<<meta", systems[-1])
        self.assertEqual(result["answer"], "Fine [S1].")


class ChatModelTests(unittest.TestCase):
    def test_messages_and_text(self) -> None:
        msgs = chat_stream._messages([{"role": "system", "content": "a"}, {"role": "user", "content": "q"},
                                      {"role": "assistant", "content": "r"}, {"role": "system", "content": "b"}])
        self.assertIsInstance(msgs[0], SystemMessage)
        self.assertEqual(msgs[0].content, "a\n\nb")
        self.assertEqual([type(m) for m in msgs[1:]], [HumanMessage, AIMessage])
        chunk = AIMessageChunk(content=[{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "Hi"}])
        self.assertEqual(chat_stream._text(chunk), "Hi")                    # thinking is never shown

    def test_provider_models_are_built_from_settings(self) -> None:
        env = {"OPENAI_API_KEY": "k", "GEMINI_API_KEY": "k", "OPENROUTER_API_KEY": "k", "GROQ_API_KEY": "k"}
        with mock.patch.dict(os.environ, env):
            cases = {"openai": "ChatOpenAI", "gemini": "ChatGoogleGenerativeAI", "openrouter": "ChatOpenAI",
                     "groq": "ChatGroq"}
            for name, cls in cases.items():
                model = chat_stream.chat_model("chat", name=name)
                self.assertEqual(type(model).__name__, cls, name)
            router = chat_stream.chat_model("chat", name="openrouter")
            self.assertIn("openrouter.ai", str(router.openai_api_base))


class ChatStreamEndpointTests(unittest.TestCase):
    def test_tokens_then_one_result(self) -> None:
        from fastapi.testclient import TestClient

        from campusyamu.api import create_app
        from campusyamu.api.auth import SupabaseAuth

        class Web:
            course_names: set[str] = set()

            def ask(self, body, user=None, on_token=None):
                for piece in ("Yes, ", "an aptitude ", "test [S1]."):
                    on_token(piece)
                return 200, {"answer": "Yes, an aptitude test [S1].", "status": "answered", "notes": [],
                             "model": "m", "career_research": False, "sources": [{"id": "S1"}]}

        app = create_app(lambda: Web(), auth=SupabaseAuth(url=""))
        with TestClient(app) as client:
            r = client.post("/v1/chat/stream", json={"question": "q", "course": {"course_code": "023"}})
            self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
            events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in r.text.strip().split("\n\n")]
            self.assertIn("/v1/chat/stream", client.get("/openapi.json").json()["paths"])
        self.assertEqual([k for k, _ in events], ["token", "token", "token", "result"])
        self.assertEqual("".join(d["text"] for k, d in events if k == "token"), "Yes, an aptitude test [S1].")
        self.assertEqual((events[-1][1]["http_status"], events[-1][1]["status"]), (200, "answered"))


if __name__ == "__main__":
    unittest.main()
