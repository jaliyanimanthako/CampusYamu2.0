"""Small OpenAI Responses API client for structured analytics."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from campusyamu.core import settings


class StructuredAnalyticsModel(Protocol):
    model: str

    def generate_json(
        self,
        developer_prompt: str,
        evidence: dict[str, Any],
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 180,
        max_output_tokens: int = 5_000,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or settings.model("career_analysis")         # models.career_analysis
        if not self.api_key:
            raise ValueError("Set OPENAI_API_KEY before using career analytics")
        self.base_url = base_url.rstrip("/")
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
        text = _response_text(response)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI returned invalid structured JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("OpenAI returned a non-object analytics response")
        return value

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CampusYamu-CareerAnalytics/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc


def _response_text(response: dict[str, Any]) -> str:
    if response.get("status") != "completed":
        detail = response.get("incomplete_details") or response.get("error")
        raise RuntimeError(f"OpenAI response did not complete: {detail}")
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "refusal":
                raise RuntimeError(f"OpenAI refused the analysis: {content.get('refusal')}")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise RuntimeError("OpenAI response contained no output text")
