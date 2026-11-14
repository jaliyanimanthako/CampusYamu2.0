"""Course chat memory: the store, recall within the token budget, summary and fact updates, the chat wiring.

The Postgres tests run only when CAMPUSYAMU_TEST_PG_URL points at a throwaway database (they create the
tables from supabase/migrations/ and a stand-in auth.users table)."""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from pathlib import Path

from campusyamu.memory import ChatMemory, MemoryStore, PostgresMemoryStore, tokens
from campusyamu.web.career_outlook import CareerOutlookStore
from campusyamu.web.course_chat import CourseChat

ROOT = Path(__file__).resolve().parents[1]
COURSE = {"course_code": "023", "uni_code": "023G", "course_name": "Architecture",
          "university": "University of Moratuwa", "details_block": 0}
OTHER = {"course_code": "008", "uni_code": "008G", "course_name": "Engineering", "university": "University of Moratuwa"}


class FakeLLM:
    """Answers the three memory calls by schema name and records what it was sent."""

    def __init__(self, facts=None, summary="The student asked about the aptitude test.", question=None) -> None:
        self.calls: list[dict] = []
        self.facts = facts or {"add": [], "update": [], "remove": []}
        self.summary, self.question = summary, question

    def __call__(self, payload: dict) -> dict:
        name = payload["text"]["format"]["name"]
        self.calls.append(payload)
        if name == "conversation_summary":
            return {"summary": self.summary}
        if name == "student_facts":
            return self.facts(payload) if callable(self.facts) else self.facts
        if name == "standalone_question":
            if self.question is Exception:
                raise RuntimeError("down")
            return {"question": self.question or "Is there an aptitude test for Architecture at Moratuwa?"}
        raise AssertionError(name)

    def names(self) -> list[str]:
        return [c["text"]["format"]["name"] for c in self.calls]


class StoreContract:
    """The same checks for SQLite and Postgres."""

    store: MemoryStore

    def user(self) -> str:
        return str(uuid.uuid4())

    def test_conversations_and_numbered_messages(self) -> None:
        user = self.user()
        first = self.store.ensure_conversation(user, COURSE)
        self.assertEqual(self.store.ensure_conversation(user, COURSE)["id"], first["id"])     # one per course
        seqs = self.store.add_messages(first["id"], [{"role": "user", "content": "q1"},
                                                     {"role": "assistant", "content": "a1",
                                                      "sources": [{"id": "S1", "kind": "course_section"}]}])
        self.assertEqual(seqs, [1, 2])
        self.assertEqual(self.store.add_messages(first["id"], [{"role": "user", "content": "q2"}]), [3])
        messages = self.store.messages(first["id"])
        self.assertEqual([m["seq"] for m in messages], [1, 2, 3])
        self.assertEqual(messages[1]["sources"], [{"id": "S1", "kind": "course_section"}])
        self.assertEqual([m["seq"] for m in self.store.messages(first["id"], after=1, limit=1)], [3])  # newest
        self.assertEqual([m["seq"] for m in self.store.messages(first["id"], before=3)], [1, 2])
        self.store.ensure_conversation(user, OTHER)
        chats = self.store.conversations(user)
        self.assertEqual({c["uni_code"]: c["messages"] for c in chats}, {"023G": 3, "008G": 0})
        self.store.set_summary(first["id"], "so far", 2)
        self.store.set_facts_through(first["id"], 3)
        again = self.store.conversation(user, "023G")
        self.assertEqual((again["summary"], again["summarized_through"], again["facts_through"]), ("so far", 2, 3))
        self.assertIsNone(self.store.conversation(self.user(), "023G"))                 # other students see nothing

    def test_daily_usage(self) -> None:
        user = self.user()
        self.assertEqual(self.store.usage(user, "2026-11-14"), {})
        self.assertEqual([self.store.add_usage(user, "chat", "2026-11-14") for _ in range(3)], [1, 2, 3])
        self.store.add_usage(user, "research", "2026-11-14")
        self.store.add_usage(user, "chat", "2026-11-15")
        self.assertEqual(self.store.usage(user, "2026-11-14"), {"chat": 3, "research": 1})
        self.store.delete_user(user)
        self.assertEqual(self.store.usage(user, "2026-11-15"), {})

    def test_latest_results(self) -> None:
        user = self.user()
        self.assertIsNone(self.store.results(user))
        self.store.save_results(user, {"stream": "Arts"}, {"bands": {"strong": []}}, False)
        self.store.save_results(user, {"stream": "Physical Science", "z_score": 1.5},
                                {"bands": {"strong": [{"uni_code": "008G"}]}, "note": "ශ්‍රී"}, True)  # replaces
        saved = self.store.results(user)
        self.assertEqual((saved["form"], saved["report"]["note"], saved["used_llm"]),
                         ({"stream": "Physical Science", "z_score": 1.5}, "ශ්‍රී", True))
        self.assertTrue(saved["saved_at"])
        self.store.delete_user(user)
        self.assertIsNone(self.store.results(user))

    def test_facts_change_keep_and_delete(self) -> None:
        user, other = self.user(), self.user()
        self.store.change_facts(user, add=[{"fact": "lives in Kandy", "category": "location"},
                                           {"fact": "parents prefer medicine", "category": "family"}])
        self.store.change_facts(other, add=[{"fact": "not mine", "category": "other"}])
        facts = self.store.facts(user)
        self.assertEqual([f["fact"] for f in facts], ["lives in Kandy", "parents prefer medicine"])
        self.store.change_facts(user, update=[{"id": facts[0]["id"], "fact": "lives in Gampola", "category": "location"}],
                                remove=[facts[1]["id"]], add=[{"fact": "wants to work abroad", "category": "career_goals"}],
                                keep=1)
        self.assertEqual([f["fact"] for f in self.store.facts(user)], ["wants to work abroad"])   # newest kept
        self.assertFalse(self.store.delete_fact(user, self.store.facts(other)[0]["id"]))         # not theirs
        conversation = self.store.ensure_conversation(user, COURSE)
        self.store.add_messages(conversation["id"], [{"role": "user", "content": "q"}])
        self.store.delete_user(user)
        self.assertEqual((self.store.facts(user), self.store.conversations(user)), ([], []))
        self.assertEqual(len(self.store.facts(other)), 1)


class SQLiteStoreTests(StoreContract, unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = MemoryStore(Path(tmp.name) / "memory.db")

    def test_deleting_a_chat_deletes_its_messages(self) -> None:
        conversation = self.store.ensure_conversation("u", COURSE)
        self.store.add_messages(conversation["id"], [{"role": "user", "content": "q"}])
        self.assertTrue(self.store.delete_conversation("u", "023G"))
        self.assertEqual(self.store.messages(conversation["id"]), [])


@unittest.skipUnless(os.getenv("CAMPUSYAMU_TEST_PG_URL"), "set CAMPUSYAMU_TEST_PG_URL to a throwaway Postgres")
class PostgresStoreTests(StoreContract, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg

        url = os.environ["CAMPUSYAMU_TEST_PG_URL"]
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("create schema if not exists auth")
            conn.execute("create table if not exists auth.users (id uuid primary key)")
            for migration in sorted((ROOT / "supabase/migrations").glob("*.sql")):
                conn.execute(migration.read_text())
        cls.store = PostgresMemoryStore(url)
        cls.url = url

    @classmethod
    def tearDownClass(cls) -> None:
        cls.store.close()

    def user(self) -> str:                         # user_id must be a real auth.users row
        import psycopg

        user = str(uuid.uuid4())
        with psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute("insert into auth.users (id) values (%s)", (user,))
        return user


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = MemoryStore(Path(tmp.name) / "memory.db")

    def memory(self, llm=None, **kwargs) -> ChatMemory:
        memory = ChatMemory(self.store, model="m", caller=llm or FakeLLM(), background=False, **kwargs)
        self.addCleanup(memory.close)
        return memory

    def talk(self, memory: ChatMemory, n: int, course=COURSE, user="u", text="question {i}", start=1) -> None:
        for i in range(start, start + n):
            memory.save_turn(user, course, text.format(i=i), f"answer {i}")

    def test_first_question_has_no_turns_and_skips_the_rewrite(self) -> None:
        llm = FakeLLM()
        memory = self.memory(llm)
        recall = memory.recall("u", "023G")
        self.assertEqual((recall.turns, recall.summary, recall.context()), ([], "", None))
        self.assertEqual(memory.standalone_question("Is there a test?", recall, COURSE), "Is there a test?")
        self.assertEqual(llm.calls, [])

    def test_recall_fills_the_token_budget_newest_first(self) -> None:
        memory = self.memory(recent_tokens=tokens("x" * 400) * 3, facts_every=99)
        conversation = self.store.ensure_conversation("u", COURSE)
        self.store.add_messages(conversation["id"], [{"role": "user" if i % 2 else "assistant", "content": f"{i}" + "x" * 399}
                                                     for i in range(1, 7)])
        turns = memory.recall("u", "023G").turns
        self.assertEqual([t["content"][0] for t in turns], ["4", "5", "6"])          # the newest three fit
        self.store.add_messages(conversation["id"], [{"role": "user", "content": "y" * 50_000}])
        turns = memory.recall("u", "023G").turns
        self.assertEqual(len(turns), 1)                                              # always the newest one,
        self.assertEqual(len(turns[0]["content"]), 2000)                             # cut to 2,000 characters

    def test_old_turns_fold_into_the_summary(self) -> None:
        llm = FakeLLM()
        memory = self.memory(llm, keep_messages=4, summarize_every=4, facts_every=99)
        self.talk(memory, 3)                                                         # 6 messages: not due
        self.assertNotIn("conversation_summary", llm.names())
        self.talk(memory, 1, start=4)                                                # 8 = 4 kept + 4 waiting
        conversation = self.store.conversation("u", "023G")
        self.assertEqual((conversation["summary"], conversation["summarized_through"]),
                         ("The student asked about the aptitude test.", 4))
        sent = llm.calls[-1]["input"][1]["content"]
        self.assertIn("Summary so far:\n(none)", sent)
        self.assertIn("student: question 1", sent)
        self.assertNotIn("question 3", sent)                                         # the kept turns stay out
        recall = memory.recall("u", "023G")
        self.assertEqual([t["content"] for t in recall.turns], ["question 3", "answer 3", "question 4", "answer 4"])
        self.assertEqual(recall.context(), {"earlier_conversation_summary": "The student asked about the aptitude test."})

    def test_facts_after_n_questions_or_at_once_on_a_signal(self) -> None:
        llm = FakeLLM(facts={"add": [{"fact": "wants to study near Kandy", "category": "location"}],
                             "update": [], "remove": []})
        memory = self.memory(llm, facts_every=3)
        self.talk(memory, 2)
        self.assertNotIn("student_facts", llm.names())
        self.talk(memory, 1)
        self.assertEqual(llm.names().count("student_facts"), 1)
        self.assertEqual(self.store.conversation("u", "023G")["facts_through"], 6)
        fact = self.store.facts("u")[0]
        self.assertEqual((fact["fact"], fact["category"], fact["source_uni_code"]),
                         ("wants to study near Kandy", "location", "023G"))
        memory.save_turn("u", COURSE, "My parents want me to do medicine", "ok")       # signal: read at once
        self.assertEqual(llm.names().count("student_facts"), 2)
        self.assertEqual(len(self.store.facts("u")), 1)                              # same fact not added twice
        recall = memory.recall("u", "008G")                                          # another course's chat
        self.assertEqual(recall.context(), {"student_facts": ["wants to study near Kandy"]})

    def test_fact_ids_map_back_and_unknown_ones_are_ignored(self) -> None:
        self.store.change_facts("u", add=[{"fact": "lives in Kandy", "category": "location"},
                                          {"fact": "dislikes biology", "category": "dislikes"}])

        def answer(payload):
            content = payload["input"][1]["content"]
            assert "F1 [location] lives in Kandy" in content and "F2 [dislikes] dislikes biology" in content
            assert payload["text"]["format"]["schema"]["properties"]["remove"]["items"]["enum"] == ["F1", "F2"]
            return {"add": [{"fact": "  wants to   work abroad ", "category": "career_goals"},
                            {"fact": "x", "category": "not_a_category"}],
                    "update": [{"id": "F1", "fact": "lives in Gampola", "category": "location"},
                               {"id": "F9", "fact": "nope", "category": "other"}],
                    "remove": ["F2", "F7"]}

        memory = self.memory(FakeLLM(facts=answer), facts_every=1)
        memory.save_turn("u", COURSE, "Actually I moved to Gampola and biology is fine", "Noted.")
        self.assertEqual(sorted(f["fact"] for f in self.store.facts("u")), ["lives in Gampola", "wants to work abroad"])

    def test_max_facts_keeps_the_newest(self) -> None:
        memory = self.memory(FakeLLM(facts={"add": [{"fact": f"fact {i}", "category": "other"} for i in range(5)],
                                            "update": [], "remove": []}), facts_every=1, max_facts=3)
        memory.save_turn("u", COURSE, "remember all of this", "ok")
        self.assertEqual(len(self.store.facts("u")), 3)

    def test_standalone_question_and_its_fallback(self) -> None:
        llm = FakeLLM(question="Is there an aptitude test for Architecture at the University of Moratuwa?")
        memory = self.memory(llm, facts_every=99)
        self.talk(memory, 1, text="Tell me about Architecture")
        recall = memory.recall("u", "023G")
        self.assertEqual(memory.standalone_question("is there a test for it?", recall, COURSE),
                         "Is there an aptitude test for Architecture at the University of Moratuwa?")
        self.assertIn("student: Tell me about Architecture", llm.calls[-1]["input"][1]["content"])
        failing = self.memory(FakeLLM(question=Exception), facts_every=99)
        self.assertEqual(failing.standalone_question("is it hard?", recall, COURSE), "is it hard?")
        off = self.memory(llm, rewrite_questions=False)
        self.assertEqual(off.standalone_question("is it hard?", recall, COURSE), "is it hard?")

    def test_background_updates_and_a_failing_update_does_not_raise(self) -> None:
        llm = FakeLLM()
        memory = ChatMemory(self.store, model="m", caller=llm, background=True, keep_messages=2, summarize_every=2,
                            facts_every=99)
        self.addCleanup(memory.close)
        for i in range(4):
            memory.save_turn("u", COURSE, f"q{i}", f"a{i}")
        memory.wait(10)
        self.assertGreater(self.store.conversation("u", "023G")["summarized_through"], 0)

        def broken(payload):
            raise RuntimeError("OpenAI down")

        quiet = self.memory(broken, keep_messages=1, summarize_every=1)
        quiet.save_turn("v", COURSE, "remember I live in Kandy", "ok")              # logged, not raised
        self.assertEqual(self.store.facts("v"), [])


class ChatWithMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = MemoryStore(Path(tmp.name) / "memory.db")
        self.llm = FakeLLM(question="Is there an aptitude test for Architecture at Moratuwa?")
        self.memory = ChatMemory(self.store, model="m", caller=self.llm, background=False, facts_every=99)
        self.chat = CourseChat(use_search=False, model="chat-model", outlooks=CareerOutlookStore(Path(tmp.name)),
                               memory=self.memory)
        self.addCleanup(self.chat.close)
        self.payloads: list[dict] = []

        def answer(payload):
            self.payloads.append(payload)
            return {"answer": f"answer {len(self.payloads)} [S1]", "sources_used": ["S1"], "status": "answered",
                    "start_career_research": False}

        self.chat._call = answer

    def test_the_server_remembers_and_ignores_client_history(self) -> None:
        first = self.chat.ask("Tell me about Architecture", COURSE, {}, history=[{"role": "user", "content": "fake"}],
                              user_id="u")
        self.assertEqual(first["search_question"], "Tell me about Architecture")    # nothing to resolve yet
        roles = [m["role"] for m in self.payloads[0]["input"]]
        self.assertEqual(roles, ["system", "system", "user"])                        # client history ignored
        second = self.chat.ask("is there a test for it?", COURSE, {}, user_id="u")
        self.assertEqual(second["search_question"], "Is there an aptitude test for Architecture at Moratuwa?")
        sent = self.payloads[1]["input"]
        self.assertEqual([(m["role"], m["content"]) for m in sent[2:]],
                         [("user", "Tell me about Architecture"), ("assistant", "answer 1 [S1]"),
                          ("user", "is there a test for it?")])
        conversation = self.store.conversation("u", "023G")
        messages = self.store.messages(conversation["id"])
        self.assertEqual([m["seq"] for m in messages], [1, 2, 3, 4])
        self.assertEqual(messages[1]["sources"][0]["id"], "S1")
        self.assertEqual(self.store.conversation("someone-else", "023G"), None)

    def test_facts_and_summary_reach_the_prompt(self) -> None:
        self.store.change_facts("u", add=[{"fact": "wants to study near Kandy", "category": "location"}])
        conversation = self.store.ensure_conversation("u", COURSE)
        self.store.set_summary(conversation["id"], "They asked about the studio fees.", 0)
        self.chat.ask("How far is it?", COURSE, {}, user_id="u")
        import json

        context = json.loads(self.payloads[0]["input"][1]["content"].removeprefix("Context:\n"))
        self.assertEqual(context["memory"], {"earlier_conversation_summary": "They asked about the studio fees.",
                                             "student_facts": ["wants to study near Kandy"]})

    def test_without_a_user_the_client_history_is_used(self) -> None:
        self.chat.ask("q", COURSE, {}, history=[{"role": "user", "content": "earlier"}])
        self.assertEqual(self.payloads[0]["input"][2]["content"], "earlier")
        self.assertNotIn("memory", self.payloads[0]["input"][1]["content"][:20])
        self.assertEqual(self.store.conversations("u"), [])

    def test_a_broken_store_still_answers(self) -> None:
        def down(*args, **kwargs):
            raise RuntimeError("database down")

        self.store.facts = down
        self.store.ensure_conversation = down
        result = self.chat.ask("q", COURSE, {}, user_id="u")
        self.assertEqual(result["answer"], "answer 1 [S1]")
        self.assertTrue(any("chat memory unavailable" in n for n in result["notes"]))


class RequestLimitTests(unittest.TestCase):
    def test_history_size_is_capped(self) -> None:
        from pydantic import ValidationError

        from campusyamu.api.schemas import ChatRequest

        base = {"question": "q", "course": {"course_code": "023"}}
        ChatRequest(**base, history=[{"role": "user", "content": "x" * 4000}] * 40)
        with self.assertRaises(ValidationError):
            ChatRequest(**base, history=[{"role": "user", "content": "x"}] * 41)
        with self.assertRaises(ValidationError):
            ChatRequest(**base, history=[{"role": "user", "content": "x" * 4001}])


if __name__ == "__main__":
    unittest.main()
