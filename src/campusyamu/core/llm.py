"""One door for every language-model call: OpenAI or Gemini, chosen by llm.provider in settings.yaml.

The code builds requests in the OpenAI Responses API shape (``input`` items, ``text.format`` JSON
schema, function tools) and reads replies in that shape. With ``llm.provider: gemini`` the request is
translated to Gemini's ``generateContent`` and the reply translated back, so callers never branch:

    from campusyamu.core import llm
    llm.call_structured(payload)        # strict JSON object (schema in payload["text"]["format"])
    llm.post_responses(payload)         # the whole Responses-shaped reply (tool calls, text)
    llm.chat_completions(payload)       # Chat Completions shape (graph-viewer chatbot)

Keys come from .env: OPENAI_API_KEY or GEMINI_API_KEY. Models: models.<provider>.<role>
(settings.model). The Gemini Decision calls (guardrail, preference engine) are separate and always
Gemini.

    uv run python -m campusyamu.core.llm --check     # three tiny paid calls against the configured provider
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import OrderedDict
from typing import Any

from . import settings

PROVIDERS = ("openai", "gemini")
KEY_NAMES = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
DEFAULT_MODELS = {"openai": "gpt-4o-mini", "gemini": "gemini-3.5-flash"}
OPENAI_URL = "https://api.openai.com/v1"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
RETRY_CODES = {429, 500, 502, 503, 504}


# --- provider and keys ----------------------------------------------------------------------
def provider() -> str:
    """llm.provider in settings.yaml: "openai" (default) or "gemini"."""

    name = str(settings.get("llm.provider") or "openai").strip().casefold()
    if name not in PROVIDERS:
        raise ValueError(f"llm.provider must be one of {PROVIDERS}, not {name!r}")
    return name


def key_name(name: str | None = None) -> str:
    return KEY_NAMES[name or provider()]


def api_key(name: str | None = None) -> str | None:
    return os.getenv(key_name(name)) or None


def available(name: str | None = None) -> bool:
    """True when the provider's key is set."""

    return bool(api_key(name))


def require_key(name: str | None = None) -> str:
    key = api_key(name)
    if not key:
        raise RuntimeError(f"{key_name(name)} is not set (llm.provider is {name or provider()})")
    return key


def label(name: str | None = None) -> str:
    return {"openai": "OpenAI", "gemini": "Gemini"}[name or provider()]


# --- Responses-shaped calls -----------------------------------------------------------------
def post_responses(payload: dict[str, Any], *, api_key: str | None = None, timeout: int = 60,
                   user_agent: str = "CampusYamu/0.1", name: str | None = None) -> dict[str, Any]:
    """Send a Responses API payload to the configured provider; return a Responses-shaped reply."""

    name = name or provider()
    key = api_key or require_key(name)
    if name == "openai":
        return post_json(f"{OPENAI_URL}/responses", payload, {"Authorization": f"Bearer {key}"},
                     timeout, user_agent, "OpenAI")
    model = payload.get("model") or settings.model("chat")
    body = post_json(f"{GEMINI_URL}/models/{model}:generateContent", gemini_request(payload),
                 {"x-goog-api-key": key}, timeout, user_agent, "Gemini")
    return gemini_to_responses(body)


def call_structured(payload: dict[str, Any], api_key: str | None = None, timeout: int = 60,
                    user_agent: str = "CampusYamu/0.1") -> dict[str, Any]:
    """POST a request whose text.format is a json_schema; return the parsed JSON object."""

    body = post_responses(payload, api_key=api_key, timeout=timeout, user_agent=user_agent)
    return structured_output(body)


def response_text(body: dict[str, Any]) -> str:
    """The output text of a Responses-shaped reply; raises on refusal or an unfinished reply."""

    if body.get("status") not in (None, "completed"):
        detail = body.get("incomplete_details") or body.get("error")
        raise RuntimeError(f"{label()} response did not complete: {detail}")
    for item in body.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) and item.get("type") == "message" else []:
            if content.get("type") == "refusal":
                raise RuntimeError(f"model refused: {content.get('refusal')}")
            if content.get("type") == "output_text":
                return str(content.get("text") or "")
    raise RuntimeError(f"no output text (status {body.get('status')})")


def structured_output(body: dict[str, Any]) -> dict[str, Any]:
    text = response_text(body)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label()} returned invalid structured JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label()} returned a non-object structured response")
    return value


# --- Chat Completions (graph-viewer chatbot) ------------------------------------------------
def chat_completions(payload: dict[str, Any], *, api_key: str | None = None, timeout: int = 60,
                     user_agent: str = "CampusYamu/0.1", name: str | None = None) -> dict[str, Any]:
    """Chat Completions request; Gemini through its OpenAI-compatible endpoint (same shape)."""

    name = name or provider()
    key = api_key or require_key(name)
    url = f"{OPENAI_URL}/chat/completions" if name == "openai" else f"{GEMINI_URL}/openai/chat/completions"
    return post_json(url, payload, {"Authorization": f"Bearer {key}"}, timeout, user_agent, label(name))


# --- HTTP -----------------------------------------------------------------------------------
def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float:
    """Retry-After when the server sends one (capped), else 2, 4, 8 ... seconds."""

    try:
        return min(float(exc.headers.get("Retry-After") or ""), 30.0)
    except (TypeError, ValueError):
        return float(2 ** (attempt + 1))


def post_json(url: str, payload: dict[str, Any], auth: dict[str, str], timeout: int, user_agent: str,
              who: str, attempts: int = 4) -> dict[str, Any]:
    """POST JSON; overload and rate-limit replies (429, 5xx) are retried with backoff (~14 s in all)."""

    data = json.dumps(payload).encode("utf-8")
    headers = {**auth, "Content-Type": "application/json", "User-Agent": user_agent}
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_CODES and attempt < attempts - 1:
                time.sleep(_retry_delay(exc, attempt))
                continue
            raise RuntimeError(f"{who} HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{who} request failed: {exc.reason}") from exc
    raise AssertionError("unreachable")


# --- Responses -> Gemini --------------------------------------------------------------------
# Gemini 3 models sign their tool calls; the signature must come back with the call on the next
# turn. Responses-shaped items carry only call_id, so signatures wait here, keyed by call_id.
_SIGNATURES: OrderedDict[str, tuple[str | None, str | None]] = OrderedDict()
_SIGNATURES_LOCK = threading.Lock()
_MAX_SIGNATURES = 4096


def _remember(call_id: str, gemini_id: str | None, signature: str | None) -> None:
    with _SIGNATURES_LOCK:
        _SIGNATURES[call_id] = (gemini_id, signature)
        while len(_SIGNATURES) > _MAX_SIGNATURES:
            _SIGNATURES.popitem(last=False)


def _recall(call_id: str) -> tuple[str | None, str | None]:
    with _SIGNATURES_LOCK:
        return _SIGNATURES.get(call_id, (None, None))


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text") or "") for p in content if isinstance(p, dict) and "text" in p)
    return "" if content is None else str(content)


def gemini_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate a Responses API payload into a Gemini generateContent body."""

    system: list[str] = [payload["instructions"]] if payload.get("instructions") else []
    contents: list[dict[str, Any]] = []
    call_names: dict[str, str] = {}

    def add(role: str, part: dict[str, Any]) -> None:
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].append(part)
        else:
            contents.append({"role": role, "parts": [part]})

    items = payload.get("input") or []
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    for item in items:
        kind = item.get("type")
        if kind == "function_call":
            call_id = str(item.get("call_id") or "")
            call_names[call_id] = str(item.get("name") or "")
            gemini_id, signature = _recall(call_id)
            try:
                args = json.loads(item.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            part: dict[str, Any] = {"functionCall": {"name": item.get("name"), "args": args,
                                                     **({"id": gemini_id} if gemini_id else {})}}
            if signature:
                part["thoughtSignature"] = signature
            add("model", part)
        elif kind == "function_call_output":
            call_id = str(item.get("call_id") or "")
            gemini_id, _ = _recall(call_id)
            output = item.get("output")
            try:
                result = json.loads(output) if isinstance(output, str) else output
            except json.JSONDecodeError:
                result = output
            add("user", {"functionResponse": {
                "name": call_names.get(call_id, ""),
                "response": result if isinstance(result, dict) else {"result": result},
                **({"id": gemini_id} if gemini_id else {})}})
        else:
            role = item.get("role", "user")
            text = _text_of(item.get("content"))
            if role in ("system", "developer"):
                system.append(text)
            elif text:
                add("model" if role == "assistant" else "user", {"text": text})

    config: dict[str, Any] = {}
    fmt = (payload.get("text") or {}).get("format") or {}
    if fmt.get("type") == "json_schema":
        config["responseMimeType"] = "application/json"
        config["responseJsonSchema"] = fmt.get("schema") or {}
    if payload.get("max_output_tokens"):
        # Gemini counts thinking tokens against this cap; the headroom keeps answers whole
        extra = int(settings.get("llm.gemini.extra_output_tokens", 4096) or 0)
        config["maxOutputTokens"] = int(payload["max_output_tokens"]) + extra
    if payload.get("temperature") is not None:
        config["temperature"] = payload["temperature"]
    thinking = settings.get("llm.gemini.thinking")
    if isinstance(thinking, bool) or thinking in (None, ""):
        pass
    elif isinstance(thinking, int):
        config["thinkingConfig"] = {"thinkingBudget": thinking}
    else:
        config["thinkingConfig"] = {"thinkingLevel": str(thinking)}

    body: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": [{"text": ""}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(s for s in system if s)}]}
    if config:
        body["generationConfig"] = config
    tools = [t for t in payload.get("tools") or [] if t.get("type") == "function"]
    if tools:
        body["tools"] = [{"functionDeclarations": [
            {"name": t["name"], "description": t.get("description", ""),
             "parametersJsonSchema": t.get("parameters") or {"type": "object", "properties": {}}}
            for t in tools]}]
    return body


def gemini_to_responses(body: dict[str, Any]) -> dict[str, Any]:
    """Translate a Gemini generateContent reply into the Responses API reply shape."""

    candidates = body.get("candidates") or []
    if not candidates:
        reason = (body.get("promptFeedback") or {}).get("blockReason") or "no candidates"
        return {"status": "completed", "output": [
            {"type": "message", "content": [{"type": "refusal", "refusal": f"Gemini blocked the request: {reason}"}]}]}
    candidate = candidates[0]
    finish = candidate.get("finishReason") or "STOP"
    texts: list[str] = []
    output: list[dict[str, Any]] = []
    for part in (candidate.get("content") or {}).get("parts") or []:
        if "functionCall" in part:
            call = part["functionCall"]
            call_id = f"call_{uuid.uuid4().hex[:24]}"
            _remember(call_id, call.get("id"), part.get("thoughtSignature"))
            output.append({"type": "function_call", "call_id": call_id, "name": call.get("name", ""),
                           "arguments": json.dumps(call.get("args") or {}, ensure_ascii=False)})
        elif "text" in part and not part.get("thought"):
            texts.append(part["text"])
    message: list[dict[str, Any]] = []
    if finish in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"):
        message.append({"type": "refusal", "refusal": f"Gemini stopped the answer ({finish})"})
    elif texts:
        message.append({"type": "output_text", "text": "".join(texts)})
    if message:
        output.insert(0, {"type": "message", "role": "assistant", "content": message})
    if finish == "MAX_TOKENS":
        return {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": output}
    return {"status": "completed", "output": output, "usage": body.get("usageMetadata")}


# --- smoke check ----------------------------------------------------------------------------
def _check() -> int:
    """Three tiny calls: structured JSON, one tool call, one embedding."""

    from campusyamu.handbook_search.embeddings import make_embedder

    name, model = provider(), settings.model("chat")
    print(f"provider {name}, chat model {model}, key {key_name()} {'set' if available() else 'MISSING'}")
    failed = 0

    def step(title: str, run) -> None:
        nonlocal failed
        try:
            print(f"{title}: OK  {run()}")
        except Exception as exc:                        # report every step, not just the first failure
            failed += 1
            print(f"{title}: FAILED  {str(exc)[:400]}")

    schema = {"type": "object", "additionalProperties": False, "required": ["answer"],
              "properties": {"answer": {"type": "string"}}}
    step(f"1. structured JSON ({model})", lambda: call_structured(
        {"model": model, "max_output_tokens": 50,
         "input": [{"role": "system", "content": "Reply in JSON."}, {"role": "user", "content": "Say ok."}],
         "text": {"format": {"type": "json_schema", "name": "check", "strict": True, "schema": schema}}}))

    tool = {"type": "function", "name": "get_time", "description": "Current time in a city", "strict": True,
            "parameters": {"type": "object", "additionalProperties": False, "required": ["city"],
                           "properties": {"city": {"type": "string"}}}}
    agent = settings.model("career_agent")
    question = {"role": "user", "content": "What time is it in Kandy? Use the tool."}

    def tool_round_trip() -> str:
        first = post_responses({"model": agent, "max_output_tokens": 200, "input": [question], "tools": [tool]})
        calls = [i for i in first["output"] if i.get("type") == "function_call"]
        if not calls:
            raise RuntimeError("the model answered without calling the tool")
        second = post_responses({"model": agent, "max_output_tokens": 200, "tools": [tool], "input": [
            question, *calls, {"type": "function_call_output", "call_id": calls[0]["call_id"],
                               "output": json.dumps({"time": "10:30"})}]})
        return f"{calls[0]['name']}{calls[0]['arguments']} -> {response_text(second)[:100]!r}"

    step(f"2. tool call ({agent})", tool_round_trip)

    def embedding() -> str:
        embedder = make_embedder(name, query=True)
        return f"{embedder.cache_id}: {len(embedder.embed(['z-score'])[0])} dimensions"

    step("3. embedding", embedding)
    if failed:
        print(f"\n{failed} of 3 failed. HTTP 503/429 = Gemini busy or rate-limited: try again in a few minutes, "
              "or set another model in models.gemini (settings.yaml). HTTP 400 = a request the model rejects.")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    from campusyamu.knowledge_graph.handbook_prose import _load_env

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="three tiny paid calls against the provider")
    parser.add_argument("--env-file")
    args = parser.parse_args()
    _load_env(args.env_file)
    if args.check:
        raise SystemExit(_check())
    print(f"provider {provider()} ({key_name()} {'set' if available() else 'MISSING'})")
