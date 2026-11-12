"""Model: one tool-calling turn at a time, via the OpenAI Responses API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..openai_client import OpenAIResponsesClient


DEFAULT_AGENT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str  # JSON text, exactly as the model produced it


@dataclass
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)


class ToolCallingModel(Protocol):
    model: str

    def step(
        self,
        instructions: str,
        items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn: ...


class OpenAIToolModel:
    """A cheap model for the loop. AGENT_MODEL overrides the default."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        max_output_tokens: int = 1_500,
        timeout_seconds: int = 120,
    ) -> None:
        self.model = model or os.getenv("AGENT_MODEL") or DEFAULT_AGENT_MODEL
        self._client = OpenAIResponsesClient(
            api_key,
            self.model,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
        )

    def step(
        self,
        instructions: str,
        items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        payload: dict[str, Any] = {
            "model": self.model,
            # The harness owns the context (it compacts it), so nothing is
            # stored server-side.
            "store": False,
            "instructions": instructions,
            "input": items,
            "max_output_tokens": self._client.max_output_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = True
        response = self._client._post_json("/responses", payload)
        if response.get("status") != "completed":
            detail = response.get("incomplete_details") or response.get("error")
            raise RuntimeError(f"Agent model turn did not complete: {detail}")
        return parse_turn(response)


def parse_turn(response: dict[str, Any]) -> ModelTurn:
    turn = ModelTurn()
    texts = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            turn.calls.append(
                ToolCall(
                    str(item.get("call_id") or ""),
                    str(item.get("name") or ""),
                    str(item.get("arguments") or "{}"),
                )
            )
        elif item.get("type") == "message":
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    texts.append(str(content.get("text") or ""))
    turn.text = "\n".join(texts).strip()
    return turn
