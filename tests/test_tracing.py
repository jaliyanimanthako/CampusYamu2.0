"""Langfuse tracing (core/tracing.py): off without keys, real SDK spans captured in memory (no network)."""

from __future__ import annotations

import contextvars
import json
import os
import threading
import unittest
import uuid
from unittest import mock

from campusyamu.core import llm, settings, tracing

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["answer"],
          "properties": {"answer": {"type": "string"}}}
PAYLOAD = {"model": "gemini-3.5-flash", "max_output_tokens": 100, "input": [{"role": "user", "content": "hi"}],
           "text": {"format": {"type": "json_schema", "name": "course_answer", "strict": True, "schema": SCHEMA}}}
GEMINI_REPLY = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"answer": "ok"}'}]}}],
                "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 200, "thoughtsTokenCount": 300,
                                  "totalTokenCount": 1500}}


def with_settings(values: dict):
    return mock.patch.object(settings, "get", lambda key, default=None: values.get(key, default))


class InMemoryLangfuse:
    """The real Langfuse client exporting spans to memory instead of a server (one key per test: the
    SDK keeps one client per public key)."""

    def __enter__(self):
        from langfuse import Langfuse
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        self.exporter = InMemorySpanExporter()
        self.client = Langfuse(public_key=f"pk-lf-test-{uuid.uuid4().hex}", secret_key="sk-lf-test", base_url="http://127.0.0.1:9",
                               span_exporter=self.exporter)
        self.patches = [mock.patch.object(tracing, "client", lambda: self.client),
                        mock.patch.object(tracing, "_broken", False)]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()
        self.client.shutdown()

    def spans(self) -> dict[str, dict]:
        self.client.flush()
        return {s.name: dict(s.attributes) for s in self.exporter.get_finished_spans()}


class TracingOffTests(unittest.TestCase):
    def test_off_without_keys_and_calls_still_work(self) -> None:
        with mock.patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": ""}):
            self.assertFalse(tracing.enabled())
            self.assertIsNone(tracing.client())
            with tracing.observe("chat", user_id="u") as obs:
                obs.update(output="x")                                   # no-op, no error
        with with_settings({"tracing.enabled": False}), \
                mock.patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"}):
            self.assertFalse(tracing.enabled())

    def test_a_langfuse_failure_never_breaks_the_call(self) -> None:
        broken = mock.Mock()
        broken.start_as_current_observation.side_effect = RuntimeError("langfuse down")
        with mock.patch.object(tracing, "client", lambda: broken), mock.patch.object(tracing, "_broken", False), \
                self.assertLogs("campusyamu.core.tracing", "WARNING"):
            with tracing.observe("chat") as obs:
                obs.update(output="still runs")
            self.assertTrue(tracing._broken)


class UsageAndCostTests(unittest.TestCase):
    def test_usage_from_every_reply_shape(self) -> None:
        self.assertEqual(tracing.usage({"usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}}),
                         {"input": 10, "output": 4, "total": 14})                     # OpenAI Responses
        self.assertEqual(tracing.usage({"usage": {"prompt_tokens": 7, "completion_tokens": 3}}),
                         {"input": 7, "output": 3, "total": 10})                      # Chat Completions
        self.assertEqual(tracing.usage({"usage": GEMINI_REPLY["usageMetadata"]}),
                         {"input": 1000, "output": 500, "total": 1500})               # Gemini: thinking is output
        self.assertEqual(tracing.usage({}), {})

    def test_cost_from_prices_or_the_provider(self) -> None:
        with with_settings({"tracing.prices": {"m": {"input": 1.0, "output": 2.0}}}):
            self.assertEqual(tracing.cost("m", {"input": 1_000_000, "output": 500_000}),
                             {"input": 1.0, "output": 1.0, "total": 2.0})
            self.assertIsNone(tracing.cost("unpriced", {"input": 5}))                 # Langfuse's price list
            self.assertEqual(tracing.cost("m", {"input": 1}, {"usage": {"cost": 0.0042}}), {"total": 0.0042})

    def test_step_names(self) -> None:
        self.assertEqual(tracing.step_name("CampusYamu-CourseChat/0.1", PAYLOAD), "CourseChat: course_answer")
        self.assertEqual(tracing.step_name("CampusYamu-Guardrail/0.1"), "Guardrail")
        self.assertEqual(tracing.step_name("CampusYamu/0.1"), "llm")


class RealSdkTests(unittest.TestCase):
    def test_llm_call_nests_under_the_request_with_user_tokens_and_cost(self) -> None:
        values = {"llm.provider": "gemini", "tracing.prices": {"gemini-3.5-flash": {"input": 1.5, "output": 9.0}}}
        with InMemoryLangfuse() as lf, with_settings(values), \
                mock.patch.object(llm, "post_json", lambda *a, **k: GEMINI_REPLY):
            with tracing.observe("chat", user_id="student-1", session_id="student-1:008B", input="hi"):
                self.assertEqual(llm.call_structured(PAYLOAD, "gk", 30, "CampusYamu-CourseChat/0.1"), {"answer": "ok"})
            spans = lf.spans()
        gen = spans["CourseChat: course_answer"]
        self.assertEqual(gen["langfuse.observation.type"], "generation")
        self.assertEqual(gen["langfuse.observation.model.name"], "gemini-3.5-flash")
        self.assertEqual(gen["user.id"], "student-1")
        self.assertEqual(gen["session.id"], "student-1:008B")
        self.assertEqual(json.loads(gen["langfuse.observation.usage_details"]),
                         {"input": 1000, "output": 500, "total": 1500})
        self.assertAlmostEqual(json.loads(gen["langfuse.observation.cost_details"])["total"],
                               1000 * 1.5 / 1e6 + 500 * 9.0 / 1e6)
        self.assertIn("ok", gen["langfuse.observation.output"])
        self.assertEqual(spans["chat"]["user.id"], "student-1")

    def test_errors_are_marked_and_raised(self) -> None:
        def fail(*a, **k):
            raise RuntimeError("Gemini HTTP 503: busy")

        with InMemoryLangfuse() as lf, with_settings({"llm.provider": "gemini"}), \
                mock.patch.object(llm, "post_json", fail):
            with self.assertRaisesRegex(RuntimeError, "503"):
                llm.call_structured(PAYLOAD, "gk", 30, "CampusYamu-Memory/0.1")
            spans = lf.spans()
        self.assertEqual(spans["Memory: course_answer"]["langfuse.observation.level"], "ERROR")
        self.assertIn("503", spans["Memory: course_answer"]["langfuse.observation.status_message"])

    def test_no_content_when_capture_is_off(self) -> None:
        with InMemoryLangfuse() as lf, with_settings({"llm.provider": "gemini", "tracing.capture_content": False}), \
                mock.patch.object(llm, "post_json", lambda *a, **k: GEMINI_REPLY):
            llm.call_structured(PAYLOAD, "gk", 30, "CampusYamu-CourseChat/0.1")
            gen = lf.spans()["CourseChat: course_answer"]
        self.assertNotIn("langfuse.observation.input", gen)
        self.assertNotIn("langfuse.observation.output", gen)
        self.assertIn("langfuse.observation.usage_details", gen)                   # tokens and cost stay

    def test_work_on_another_thread_stays_in_the_trace(self) -> None:
        with InMemoryLangfuse() as lf, with_settings({"llm.provider": "gemini"}), \
                mock.patch.object(llm, "post_json", lambda *a, **k: GEMINI_REPLY):
            with tracing.observe("chat", user_id="student-2"):
                worker = threading.Thread(target=tracing.bind(llm.call_structured),
                                          args=(PAYLOAD, "gk", 30, "CampusYamu-Guardrail/0.1"))
                worker.start()
                worker.join()
            spans = lf.spans()
        self.assertEqual(spans["Guardrail: course_answer"]["user.id"], "student-2")

    def test_bind_copies_the_context(self) -> None:
        var: contextvars.ContextVar[str] = contextvars.ContextVar("v", default="none")
        var.set("request")
        seen: list[str] = []
        worker = threading.Thread(target=tracing.bind(lambda: seen.append(var.get())))
        worker.start()
        worker.join()
        self.assertEqual(seen, ["request"])


if __name__ == "__main__":
    unittest.main()
