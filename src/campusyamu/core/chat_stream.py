"""Streaming chat answers through LangChain, for whichever llm.provider is configured.

`llm.py` stays the layer for structured calls (strict JSON schemas); this module is only for text that a
student watches appear: the course chat answer (POST /v1/chat/stream). It builds the LangChain chat model
for the provider with the same settings `llm.py` uses:

* openai      ChatOpenAI                                (OPENAI_API_KEY)
* gemini      ChatGoogleGenerativeAI, llm.gemini.thinking (GEMINI_API_KEY)
* openrouter  ChatOpenAI against openrouter.ai/api/v1, llm.openrouter.reasoning (OPENROUTER_API_KEY)
* groq        ChatGroq, llm.groq.reasoning               (GROQ_API_KEY)

`stream_text` sends the messages, calls `on_token` with each piece of text as it arrives, and returns the
whole text. One Langfuse generation per call (when tracing is configured), like `llm.post_responses`.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from . import llm, settings, tracing

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 90


def _messages(items: Iterable[dict[str, Any]]) -> list[Any]:
    """Responses-style {"role", "content"} items -> LangChain messages (system parts merged first)."""

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    system, turns = [], []
    for item in items:
        role, content = item.get("role"), str(item.get("content") or "")
        if role in ("system", "developer"):
            system.append(content)
        elif role == "assistant":
            turns.append(AIMessage(content))
        elif content:
            turns.append(HumanMessage(content))
    return ([SystemMessage("\n\n".join(s for s in system if s))] if system else []) + turns


def _reasoning(name: str) -> dict[str, Any]:
    value = settings.get(f"llm.{name}.reasoning")
    if isinstance(value, bool) or value in (None, ""):
        return {}
    if isinstance(value, int):
        return {"extra_body": {"reasoning": {"max_tokens": value}}} if name == "openrouter" else {}
    return {"reasoning_effort": str(value)}


def chat_model(role: str = "chat", *, max_tokens: int = 1500, name: str | None = None,
               timeout: int = DEFAULT_TIMEOUT) -> Any:
    """The LangChain chat model for `role` (models.<provider>.<role> in settings.yaml)."""

    name = name or llm.provider()
    model = settings.model(role, provider=name)
    key = llm.require_key(name)
    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        extra = int(settings.get("llm.gemini.extra_output_tokens", 4096) or 0)   # thinking counts here
        thinking = settings.get("llm.gemini.thinking")
        config: dict[str, Any] | None = None
        if isinstance(thinking, int) and not isinstance(thinking, bool):
            config = {"thinking_budget": thinking}
        elif thinking not in (None, "") and not isinstance(thinking, bool):
            config = {"thinking_level": str(thinking)}
        return ChatGoogleGenerativeAI(model=model, google_api_key=key, max_output_tokens=max_tokens + extra,
                                      timeout=timeout, max_retries=2, include_thoughts=False,
                                      **({"thinking_config": config} if config else {}))
    if name == "groq":
        from langchain_groq import ChatGroq

        extra = int(settings.get("llm.groq.extra_output_tokens", 0) or 0)
        return ChatGroq(model=model, groq_api_key=key, max_tokens=max_tokens + extra, request_timeout=timeout,
                        max_retries=2, **_reasoning("groq"))
    from langchain_openai import ChatOpenAI

    if name == "openrouter":
        extra = int(settings.get("llm.openrouter.extra_output_tokens", 0) or 0)
        return ChatOpenAI(model=model, api_key=key, base_url=OPENROUTER_BASE_URL, max_tokens=max_tokens + extra,
                          request_timeout=timeout, max_retries=2, stream_usage=True, **_reasoning("openrouter"))
    return ChatOpenAI(model=model, api_key=key, max_tokens=max_tokens, request_timeout=timeout, max_retries=2,
                      stream_usage=True)


def _text(chunk: Any) -> str:
    """The visible text of one streamed chunk (thinking / reasoning parts are skipped)."""

    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") in (None, "text") and part.get("text"):
            parts.append(str(part["text"]))
    return "".join(parts)


def stream_text(messages: Iterable[dict[str, Any]], on_token: Callable[[str], None], *, role: str = "chat",
                max_tokens: int = 1500, step: str = "chat_answer_stream", model: Any = None) -> str:
    """Stream one answer: `on_token(piece)` per piece of text; returns the whole text.

    `model` lets tests pass a fake LangChain chat model; normally it is built from settings.
    """

    items = list(messages)
    name = llm.provider()
    llm_model = model if model is not None else chat_model(role, max_tokens=max_tokens, name=name)
    model_name = getattr(llm_model, "model", None) or getattr(llm_model, "model_name", None) or str(role)
    with tracing.generation(step, model=str(model_name), provider=name, input=items,
                            model_parameters={"max_tokens": max_tokens, "stream": True}) as gen:
        pieces: list[str] = []
        usage: dict[str, int] = {}
        for chunk in llm_model.stream(_messages(items)):
            text = _text(chunk)
            if text:
                pieces.append(text)
                on_token(text)
            meta = getattr(chunk, "usage_metadata", None) or {}
            for k_in, k_out in (("input_tokens", "input"), ("output_tokens", "output")):
                if meta.get(k_in):
                    usage[k_out] = usage.get(k_out, 0) + int(meta[k_in])
        answer = "".join(pieces)
        if usage:
            usage["total"] = usage.get("input", 0) + usage.get("output", 0)
        gen.done(None, output=answer, counts=usage or None)
        return answer
