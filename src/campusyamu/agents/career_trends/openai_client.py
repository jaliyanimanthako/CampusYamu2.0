"""Small Responses-format client for structured analytics, sent to llm.provider (OpenAI, Gemini, OpenRouter or Groq)."""

from __future__ import annotations

import json
from typing import Any, Protocol

from campusyamu.core import llm, settings


class StructuredAnalyticsModel(Protocol):
    model: str

    def generate_json(
        self,
        developer_prompt: str,
        evidence: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class ResponsesClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        timeout_seconds: int = 180,
        max_output_tokens: int = 5_000,
    ) -> None:
        self.provider = llm.provider()
        self.api_key = api_key or llm.api_key()
        self.model = model or settings.model("career_analysis")         # models.<provider>.career_analysis
        if not self.api_key:
            raise ValueError(f"Set {llm.key_name()} before using career analytics")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens

    def generate_json(
        self,
        developer_prompt: str,
        evidence: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._post_json(
            "/responses",
            {
                "model": self.model,
                "store": False,
                "max_output_tokens": self.max_output_tokens,
                "input": [
                    {
                        "role": "developer",
                        "content": [
                            {"type": "input_text", "text": developer_prompt}
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": json.dumps(evidence, ensure_ascii=False),
                            }
                        ],
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "future_career_swot",
                        "strict": True,
                        "schema": schema,
                    }
                },
            },
        )
        return llm.structured_output(response)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if path != "/responses":
            raise ValueError(f"unsupported path {path!r}")
        return llm.post_responses(payload, api_key=self.api_key, timeout=self.timeout_seconds,
                                  user_agent="CampusYamu-CareerAnalytics/0.1", name=self.provider)


OpenAIResponsesClient = ResponsesClient          # the old name
