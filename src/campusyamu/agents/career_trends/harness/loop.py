"""Agent loop: model turn, guarded tool calls, context compaction, guarded finish."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from .context import ContextManager
from .guardrails import Guardrails
from .model import ToolCallingModel
from .tools import ToolRegistry


EventCallback = Callable[[dict[str, Any]], None]


@dataclass
class AgentResult:
    # satisfied: every guardrail passed.
    # partial: finished, but some gaps could not be filled (listed in gaps).
    # stopped_at_limit: hit max_iterations before an acceptable answer.
    status: str
    answer: str
    iterations: int
    compactions: int
    gaps: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)


class AgentLoop:
    def __init__(
        self,
        model: ToolCallingModel,
        tools: ToolRegistry,
        context: ContextManager,
        guardrails: Guardrails,
        *,
        instructions: str,
        max_iterations: int = 9,
        max_calls_per_turn: int | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self.model = model
        self.tools = tools
        self.context = context
        self.guardrails = guardrails
        self.instructions = instructions
        self.max_iterations = max_iterations
        # Limiting calls per turn makes the agent read results before
        # spending the rest of its budget, so it can refine its searches.
        self.max_calls_per_turn = max_calls_per_turn
        self.on_event = on_event

    def run(self, task: str) -> AgentResult:
        self.context.start(task)
        rejections: list[str] = []
        for iteration in range(1, self.max_iterations + 1):
            turn = self.model.step(self.instructions, self.context.items, self.tools.schemas())
            self.context.add_turn(turn)
            self._emit("agent_iteration", iteration=iteration, tool_calls=len(turn.calls))

            if turn.calls:
                for index, call in enumerate(turn.calls):
                    reason = (
                        f"At most {self.max_calls_per_turn} tool calls per turn. Read these "
                        "results first, then decide what to search next."
                        if self.max_calls_per_turn and index >= self.max_calls_per_turn
                        else self.guardrails.check_call(call)
                    )
                    if reason:
                        rejections.append(reason)
                        self._emit("agent_call_rejected", tool=call.name, reason=reason)
                        output = json.dumps({"rejected_by_guardrail": reason})
                    else:
                        output = self.tools.execute(call.name, call.arguments)
                    self.context.add_tool_result(call.call_id, output)
            else:
                problems = self.guardrails.check_finish(turn.text)
                if not problems:
                    status = self.guardrails.final_status()
                    self._emit("agent_finished", status=status, iterations=iteration)
                    return AgentResult(
                        status,
                        turn.text,
                        iteration,
                        self.context.compactions,
                        self.guardrails.open_gaps(),
                        rejections,
                    )
                rejections.extend(problems)
                self._emit("agent_answer_rejected", problems=problems)
                self.context.add_user(
                    "Not accepted yet. Fix these, then answer again:\n"
                    + "\n".join(f"- {problem}" for problem in problems)
                )

            self.context.end_iteration()
            if iteration < self.max_iterations and self.context.should_compact():
                before = self.context.size()
                self.context.compact(self.model, self.guardrails.state_note)
                self._emit(
                    "agent_compacted",
                    chars_before=before,
                    chars_after=self.context.size(),
                )

        self._emit("agent_finished", status="stopped_at_limit", iterations=self.max_iterations)
        return AgentResult(
            "stopped_at_limit",
            "",
            self.max_iterations,
            self.context.compactions,
            self.guardrails.open_gaps(),
            rejections,
        )

    def _emit(self, event: str, **fields: Any) -> None:
        if self.on_event:
            self.on_event({"event": event, **fields})
