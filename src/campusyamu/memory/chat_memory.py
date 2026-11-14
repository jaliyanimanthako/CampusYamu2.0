"""Memory for the course chat, per student (user_id) and course offering (uni_code).

For each question (CourseChat.ask with a user_id):

    recall()               the student's facts (from all their course chats) + this chat's running summary
                           + the newest turns word for word, as many as fit memory.recent_tokens
    standalone_question()  the question rewritten to stand alone ("is it hard?" -> "Is it hard to get into
                           Engineering at the University of Moratuwa?"), used for the handbook search only;
                           skipped on the first question
    save_turn()            stores the question and the answer, then runs update() in the background:
        summary  once memory.summarize_every messages are waiting beyond the newest memory.keep_messages,
                 those older ones are folded into the summary (one small LLM call)
        facts    after memory.facts_every questions, or at once when the student says something like
                 "remember", "my parents ...", "I live ...", one small LLM call updates the fact list

The model for the small calls is models.memory (MEMORY_MODEL). Prompts: campusyamu/prompts/memory.py.
Token counts are estimates (about 4 characters per token), which is enough for a budget.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from campusyamu.core import settings
from campusyamu.core.openai_client import call_structured
from campusyamu.prompts import memory as prompts

from .store import MemoryStore, open_store

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
RECENT_TOKENS = settings.get("memory.recent_tokens", 2000)
KEEP_MESSAGES = settings.get("memory.keep_messages", 8)
SUMMARIZE_EVERY = settings.get("memory.summarize_every", 8)
FACTS_EVERY = settings.get("memory.facts_every", 5)
MAX_FACTS = settings.get("memory.max_facts", 30)
REWRITE_QUESTIONS = settings.get("memory.rewrite_questions", True)
MAX_TURN_CHARS = 2000            # one stored message, as given back to the model
MAX_SUMMARY_CHARS = 1500
MAX_FACT_CHARS = 200
RECALL_SCAN = 60                 # newest unsummarised messages looked at when filling the budget
FACT_SCAN = 30                   # newest messages read when looking for facts
CATEGORIES = ("location", "family", "finances", "career_goals", "interests", "dislikes", "constraints",
              "academics", "other")
# said by the student -> look for facts now instead of waiting for facts_every questions
FACT_SIGNALS = re.compile(
    r"\b(remember|don'?t forget|keep in mind|from now on|note that|my (parents|family|mother|father|mom|dad)|"
    r"i live|i'm from|i am from|i prefer|i'd prefer|i would prefer|i (don'?t|do not) want|i can'?t afford|"
    r"i cannot afford|i want to (become|be|work|study))\b", re.IGNORECASE)


def tokens(text: str) -> int:
    """Rough token count (about 4 characters per token in English)."""

    return len(text) // 4 + 1


def _clean(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _label(conversation_or_course: dict[str, Any]) -> str:
    c = conversation_or_course
    name = c.get("course_name") or c.get("course_code") or "this course"
    return f"{name} ({c.get('uni_code')}) at {c.get('university') or 'the university'}"


def _speaker(message: dict[str, Any]) -> str:
    return "student" if message["role"] == "user" else "advisor"


@dataclass
class Recall:
    """What the model gets from memory for one question."""

    conversation: dict[str, Any] | None = None
    turns: list[dict[str, str]] = field(default_factory=list)     # word for word, oldest first
    summary: str = ""
    facts: list[dict[str, Any]] = field(default_factory=list)

    def context(self) -> dict[str, Any] | None:
        """The `memory` part of the chat prompt's context, or None when there is nothing to add."""

        out: dict[str, Any] = {}
        if self.summary:
            out["earlier_conversation_summary"] = self.summary
        if self.facts:
            out["student_facts"] = [f["fact"] for f in self.facts]
        return out or None


class ChatMemory:
    def __init__(self, store: MemoryStore | None = None, model: str | None = None,
                 caller: Callable[[dict[str, Any]], dict[str, Any]] | None = None, background: bool = True,
                 recent_tokens: int = RECENT_TOKENS, keep_messages: int = KEEP_MESSAGES,
                 summarize_every: int = SUMMARIZE_EVERY, facts_every: int = FACTS_EVERY,
                 max_facts: int = MAX_FACTS, rewrite_questions: bool = REWRITE_QUESTIONS) -> None:
        self._store = store
        self.model = model or settings.model("memory", "MEMORY_MODEL", DEFAULT_MODEL)
        self._caller = caller
        self.recent_tokens, self.keep_messages = recent_tokens, keep_messages
        self.summarize_every, self.facts_every, self.max_facts = summarize_every, facts_every, max_facts
        self.rewrite_questions = rewrite_questions
        self._executor = ThreadPoolExecutor(2, thread_name_prefix="campusyamu-memory") if background else None
        self._lock = threading.Lock()
        self._busy: set[str] = set()                    # user_ids being updated
        self._again: dict[str, set[str]] = {}           # user_id -> uni_codes to update after the current run
        self._futures: list[Future] = []

    @property
    def store(self) -> MemoryStore:
        """Opened on first use (no database file or connection until the chat needs one)."""

        if self._store is None:
            self._store = open_store()
        return self._store

    # --- LLM ----------------------------------------------------------------------------
    def _call(self, system: str, content: str, name: str, schema: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        payload = {
            "model": self.model, "store": False, "max_output_tokens": max_tokens,
            "input": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}},
        }
        if self._caller is not None:
            return self._caller(payload)
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return call_structured(payload, key, 60, "CampusYamu-Memory/0.1")

    # --- before the answer ----------------------------------------------------------------
    def recall(self, user_id: str, uni_code: str) -> Recall:
        facts = self.store.facts(user_id)
        conversation = self.store.conversation(user_id, uni_code)
        if conversation is None:
            return Recall(facts=facts)
        waiting = self.store.messages(conversation["id"], after=conversation["summarized_through"],
                                      limit=RECALL_SCAN)
        turns: list[dict[str, str]] = []
        used = 0
        for message in reversed(waiting):                       # newest first, until the budget is spent
            text = message["content"][:MAX_TURN_CHARS]
            cost = tokens(text)
            if turns and used + cost > self.recent_tokens:
                break
            turns.append({"role": message["role"], "content": text})
            used += cost
        turns.reverse()
        return Recall(conversation=conversation, turns=turns, summary=conversation["summary"], facts=facts)

    def standalone_question(self, question: str, recall: Recall, course: dict[str, Any]) -> str:
        """The question rewritten to stand alone, for the handbook search; the question itself when there is
        nothing earlier, when rewriting is off, or when the call fails."""

        if not self.rewrite_questions or not (recall.turns or recall.summary):
            return question
        earlier = "\n".join(f"{_speaker(t)}: {_clean(t['content'], 600)}" for t in recall.turns[-6:])
        content = (f"Course: {_label(course)}\n"
                   + (f"Summary of the earlier conversation: {recall.summary}\n" if recall.summary else "")
                   + f"Earlier conversation:\n{earlier or '(none)'}\n\nLatest message: {question}")
        schema = {"type": "object", "additionalProperties": False, "required": ["question"],
                  "properties": {"question": {"type": "string"}}}
        try:
            rewritten = _clean(self._call(prompts.STANDALONE_QUESTION, content, "standalone_question", schema,
                                          200).get("question"), 300)
        except Exception as exc:                                # the search still works with the raw question
            log.warning("question rewrite failed: %s", exc)
            return question
        return rewritten or question

    # --- after the answer ---------------------------------------------------------------
    def save_turn(self, user_id: str, course: dict[str, Any], question: str, answer: str,
                  sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        conversation = self.store.ensure_conversation(user_id, course)
        self.store.add_messages(conversation["id"], [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer, "sources": sources or []},
        ])
        self._schedule(user_id, str(course["uni_code"]))
        return conversation

    def _schedule(self, user_id: str, uni_code: str) -> None:
        if self._executor is None:
            self._update_quietly(user_id, uni_code)
            return
        with self._lock:
            if user_id in self._busy:                           # one update per student at a time
                self._again.setdefault(user_id, set()).add(uni_code)
                return
            self._busy.add(user_id)
        self._futures = [f for f in self._futures if not f.done()]
        self._futures.append(self._executor.submit(self._work, user_id, uni_code))

    def _work(self, user_id: str, uni_code: str) -> None:
        pending = {uni_code}
        while pending:
            for code in pending:
                self._update_quietly(user_id, code)
            with self._lock:
                pending = self._again.pop(user_id, set())
                if not pending:
                    self._busy.discard(user_id)

    def _update_quietly(self, user_id: str, uni_code: str) -> None:
        try:
            self.update(user_id, uni_code)
        except Exception as exc:                                # memory must never break the chat
            log.warning("memory update failed for %s: %s", uni_code, exc)

    def wait(self, timeout: float | None = None) -> None:
        """Block until the background updates started so far are done (CLI and tests)."""

        for future in list(self._futures):
            future.result(timeout)

    def update(self, user_id: str, uni_code: str) -> dict[str, Any]:
        """Fold old turns into the summary and refresh the student's facts, each only when due."""

        done: dict[str, Any] = {"summarized_through": None, "facts": None}
        conversation = self.store.conversation(user_id, uni_code)
        if conversation is None:
            return done
        waiting = self.store.messages(conversation["id"], after=conversation["summarized_through"])
        if len(waiting) >= self.keep_messages + self.summarize_every:
            fold = waiting[:len(waiting) - self.keep_messages]
            summary = self._summarize(conversation, fold)
            self.store.set_summary(conversation["id"], summary, fold[-1]["seq"])
            done["summarized_through"] = fold[-1]["seq"]
        new = self.store.messages(conversation["id"], after=conversation["facts_through"])
        asked = [m for m in new if m["role"] == "user"]
        if asked and (len(asked) >= self.facts_every or any(FACT_SIGNALS.search(m["content"]) for m in asked)):
            done["facts"] = self._refresh_facts(user_id, conversation, new[-FACT_SCAN:])
            self.store.set_facts_through(conversation["id"], new[-1]["seq"])
        return done

    def _summarize(self, conversation: dict[str, Any], messages: list[dict[str, Any]]) -> str:
        lines = "\n".join(f"{_speaker(m)}: {m['content'][:MAX_TURN_CHARS]}" for m in messages)
        content = (f"Course: {_label(conversation)}\n\nSummary so far:\n{conversation['summary'] or '(none)'}\n\n"
                   f"Next turns:\n{lines}")
        schema = {"type": "object", "additionalProperties": False, "required": ["summary"],
                  "properties": {"summary": {"type": "string"}}}
        summary = str(self._call(prompts.CONVERSATION_SUMMARY, content, "conversation_summary", schema,
                                 500).get("summary") or "").strip()
        return summary[:MAX_SUMMARY_CHARS] or conversation["summary"]

    def _refresh_facts(self, user_id: str, conversation: dict[str, Any],
                       messages: list[dict[str, Any]]) -> dict[str, int]:
        facts = self.store.facts(user_id)
        ids = {f"F{i}": f["id"] for i, f in enumerate(facts, 1)}
        kept = "\n".join(f"F{i} [{f['category']}] {f['fact']}" for i, f in enumerate(facts, 1)) or "(none)"
        lines = "\n".join(f"{_speaker(m)}: {_clean(m['content'], MAX_TURN_CHARS if m['role'] == 'user' else 400)}"
                          for m in messages)
        content = (f"Chat about: {_label(conversation)}\n\nFacts kept so far:\n{kept}\n\n"
                   f"Latest chat lines:\n{lines}")
        fact_id = {"type": "string", "enum": list(ids)} if ids else {"type": "string"}
        item = {"type": "object", "additionalProperties": False, "required": ["fact", "category"],
                "properties": {"fact": {"type": "string"}, "category": {"type": "string", "enum": list(CATEGORIES)}}}
        schema = {
            "type": "object", "additionalProperties": False, "required": ["add", "update", "remove"],
            "properties": {
                "add": {"type": "array", "items": item},
                "update": {"type": "array", "items": {**item, "required": ["id", "fact", "category"],
                                                      "properties": {"id": fact_id, **item["properties"]}}},
                "remove": {"type": "array", "items": fact_id},
            },
        }
        raw = self._call(prompts.STUDENT_FACTS, content, "student_facts", schema, 600)
        known = {_clean(f["fact"], MAX_FACT_CHARS).casefold() for f in facts}
        add, update = [], []
        for entry in raw.get("add") or []:
            text = _clean(entry.get("fact"), MAX_FACT_CHARS)
            if text and text.casefold() not in known and entry.get("category") in CATEGORIES:
                known.add(text.casefold())
                add.append({"fact": text, "category": entry["category"], "source_uni_code": conversation["uni_code"]})
        for entry in raw.get("update") or []:
            text = _clean(entry.get("fact"), MAX_FACT_CHARS)
            if entry.get("id") in ids and text and entry.get("category") in CATEGORIES:
                update.append({"id": ids[entry["id"]], "fact": text, "category": entry["category"]})
        remove = [ids[i] for i in raw.get("remove") or [] if i in ids]
        self.store.change_facts(user_id, add=add, update=update, remove=remove, keep=self.max_facts)
        return {"added": len(add), "updated": len(update), "removed": len(remove)}

    def close(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)
        if self._store is not None:
            self._store.close()
