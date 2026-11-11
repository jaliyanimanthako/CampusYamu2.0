"""Context management: the conversation the model sees, compacted on a schedule.

Every ``compact_every`` iterations the transcript (tool calls and raw search
results) is replaced by the model's own short notes plus an authoritative
state summary written by the harness. Facts the harness tracks in code
(searches made, sources held, open gaps) therefore survive compaction even if
the model's notes are lossy.
"""

from __future__ import annotations

from typing import Any, Callable

from .model import ModelTurn, ToolCallingModel


SUMMARY_PROMPT = """
Your working context is about to be cleared. Write notes for yourself so you
can continue: what you have found so far (with source IDs), which searches
did not help, and what you still plan to look for. At most 150 words. Plain
text only. Do not add anything that is not in the conversation.
""".strip()


class ContextManager:
    def __init__(self, compact_every: int = 3) -> None:
        if compact_every < 1:
            raise ValueError("compact_every must be at least 1")
        self.compact_every = compact_every
        self.items: list[dict[str, Any]] = []
        self.task = ""
        self.notes = ""
        self.compactions = 0
        self._since_compaction = 0

    def start(self, task: str) -> None:
        self.task = task
        self.items = [_user(task)]
        self.notes = ""
        self.compactions = 0
        self._since_compaction = 0

    def add_turn(self, turn: ModelTurn) -> None:
        if turn.text:
            self.items.append({"role": "assistant", "content": turn.text})
        for call in turn.calls:
            self.items.append(
                {
                    "type": "function_call",
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
            )

    def add_tool_result(self, call_id: str, output: str) -> None:
        self.items.append({"type": "function_call_output", "call_id": call_id, "output": output})

    def add_user(self, text: str) -> None:
        self.items.append(_user(text))

    def end_iteration(self) -> None:
        self._since_compaction += 1

    def should_compact(self) -> bool:
        return self._since_compaction >= self.compact_every

    def size(self) -> int:
        """Approximate context size in characters."""

        return sum(len(str(item)) for item in self.items)

    def compact(self, model: ToolCallingModel, state_note: Callable[[], str]) -> None:
        # Called only at the end of an iteration, so every tool call already
        # has its output and the transcript can be dropped whole.
        turn = model.step(SUMMARY_PROMPT, [*self.items, _user("Write your notes now.")], [])
        self.notes = turn.text.strip()
        self.items = [
            _user(self.task),
            _user(
                "Your context was compacted. Your notes from earlier work:\n"
                f"{self.notes or '(none)'}\n\n"
                "Current state from the harness (authoritative):\n"
                f"{state_note()}"
            ),
        ]
        self.compactions += 1
        self._since_compaction = 0


def _user(text: str) -> dict[str, Any]:
    return {"role": "user", "content": text}
