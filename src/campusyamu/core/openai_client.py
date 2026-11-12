"""Minimal OpenAI Responses API call returning strict-JSON output (stdlib only)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

RESPONSES_URL = "https://api.openai.com/v1/responses"


def call_structured(payload: dict[str, Any], api_key: str, timeout: int = 60,
                    user_agent: str = "CampusYamu/0.1", url: str = RESPONSES_URL) -> dict[str, Any]:
    """POST a Responses request whose text.format is a json_schema; return the parsed object."""

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc
    for item in body.get("output", []):
        for content in item.get("content", []) if item.get("type") == "message" else []:
            if content.get("type") == "refusal":
                raise RuntimeError(f"model refused: {content.get('refusal')}")
            if content.get("type") == "output_text":
                return json.loads(content["text"])
    raise RuntimeError(f"no structured output (status {body.get('status')})")
