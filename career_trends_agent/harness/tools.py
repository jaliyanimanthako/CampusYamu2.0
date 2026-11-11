"""Tool registry: the only actions the agent can take."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    # Strict JSON schema: every property required, no extra properties.
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...] = ()) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        """Function-tool definitions in the OpenAI Responses API format."""

        return [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "strict": True,
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, arguments: str) -> str:
        """Run a tool. Errors are returned to the model as text, never raised."""

        tool = self._tools.get(name)
        if tool is None:
            return _error(f"Unknown tool {name!r}; available: {', '.join(self._tools)}")
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return _error("Arguments were not valid JSON")
        if not isinstance(args, dict):
            return _error("Arguments must be a JSON object")
        missing = set(tool.parameters.get("required", [])) - set(args)
        if missing:
            return _error(f"Missing arguments: {', '.join(sorted(missing))}")
        try:
            return tool.handler(args)
        except Exception as exc:  # The agent should see the failure and adapt.
            return _error(f"{name} failed: {exc}")


def _error(message: str) -> str:
    return json.dumps({"error": message})
