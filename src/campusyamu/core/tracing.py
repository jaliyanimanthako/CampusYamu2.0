"""Optional Langfuse tracing: every language-model call, embedding and Gemini Decision question, with
tokens, cost and errors, grouped per API request and tagged with the signed-in student.

Off unless LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set (.env); LANGFUSE_HOST points at your
Langfuse (self-hosted: e.g. http://localhost:3000). Settings: `tracing:` in config/settings.yaml.
Tracing never breaks a request: any Langfuse error is logged once and the call goes on untraced.

    with tracing.observe("chat", user_id=uid, session_id=sid, input=question) as obs:
        ...                                   # every llm / embedding call inside nests under "chat"
        obs.update(output=answer)

    pool.submit(tracing.bind(fn), *args)      # keep the trace when work moves to another thread
"""

from __future__ import annotations

import atexit
import contextlib
import contextvars
import functools
import logging
import os
import threading
from typing import Any, Callable, Iterator

from . import settings

log = logging.getLogger(__name__)

_client: Any = None
_lock = threading.Lock()
_broken = False                     # set after the first Langfuse failure: stay off for this process
CONTENT_KEYS = ("input", "output")


def enabled() -> bool:
    if settings.get("tracing.enabled", True) is False:
        return False
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")) and not _broken


def _warn(exc: BaseException) -> None:
    global _broken
    if not _broken:
        log.warning("Langfuse tracing off for this run: %s", exc)
    _broken = True


def client() -> Any:
    """The Langfuse client, created on first use; None when tracing is off."""

    global _client
    if not enabled():
        return None
    if _client is None:
        with _lock:
            if _client is None:
                try:
                    from langfuse import Langfuse

                    rate = settings.get("tracing.sample_rate", 1.0)
                    _client = Langfuse(
                        public_key=os.environ["LANGFUSE_PUBLIC_KEY"], secret_key=os.environ["LANGFUSE_SECRET_KEY"],
                        base_url=os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or None,
                        environment=settings.get("tracing.environment") or None,
                        sample_rate=float(rate) if rate is not None else None)
                    atexit.register(flush)
                except Exception as exc:
                    _warn(exc)
                    return None
    return _client


def flush() -> None:
    """Send what is buffered (at shutdown; CLI runs flush at exit on their own)."""

    if _client is not None:
        try:
            _client.flush()
        except Exception as exc:
            _warn(exc)


def _capture() -> bool:
    return settings.get("tracing.capture_content", True) is not False


def _clean(fields: dict[str, Any]) -> dict[str, Any]:
    fields = {k: v for k, v in fields.items() if v is not None}
    if not _capture():
        for key in CONTENT_KEYS:
            fields.pop(key, None)
    return fields


class Observation:
    """A traced step; update() never raises. The no-op one stands in when tracing is off."""

    def __init__(self, span: Any = None) -> None:
        self._span = span

    def update(self, **fields: Any) -> None:
        if self._span is None:
            return
        try:
            self._span.update(**_clean(fields))
        except Exception as exc:
            _warn(exc)


@contextlib.contextmanager
def observe(name: str, *, as_type: str = "span", user_id: str | None = None, session_id: str | None = None,
            tags: list[str] | None = None, **fields: Any) -> Iterator[Observation]:
    """A traced step (a new trace at the top level). user_id / session_id / tags apply to all its children.
    An exception inside is recorded on the step (level ERROR) and re-raised."""

    lf = client()
    if lf is None:
        yield Observation()
        return
    stack = contextlib.ExitStack()
    try:
        span = stack.enter_context(lf.start_as_current_observation(name=name, as_type=as_type, **_clean(fields)))
        if user_id or session_id or tags:
            from langfuse import propagate_attributes

            stack.enter_context(propagate_attributes(user_id=user_id, session_id=session_id, tags=tags))
    except Exception as exc:
        stack.close()
        _warn(exc)
        yield Observation()
        return
    observation = Observation(span)
    with stack:
        try:
            yield observation
        except BaseException as exc:
            observation.update(level="ERROR", status_message=str(exc)[:500])
            raise


def bind(fn: Callable[..., Any]) -> Callable[..., Any]:
    """`fn` running in a copy of the current context, so work handed to a thread stays in this trace."""

    context = contextvars.copy_context()

    @functools.wraps(fn)
    def run(*args: Any, **kwargs: Any) -> Any:
        return context.copy().run(fn, *args, **kwargs)

    return run


# --- language-model calls ------------------------------------------------------------------
def step_name(user_agent: str, payload: dict[str, Any] | None = None) -> str:
    """'CampusYamu-CourseChat/0.1' + schema 'course_answer' -> 'CourseChat: course_answer'."""

    who = (user_agent or "").split("/", 1)[0].removeprefix("CampusYamu-").removeprefix("CampusYamu") or "llm"
    fmt = (((payload or {}).get("text") or {}).get("format") or {}).get("name")
    return f"{who}: {fmt}" if fmt else who


def usage(body: dict[str, Any] | None) -> dict[str, int]:
    """Token counts from an OpenAI Responses, Chat Completions or Gemini usage block, as input/output/total.
    Gemini bills thinking tokens as output, so they are counted there."""

    raw = (body or {}).get("usage") or (body or {}).get("usageMetadata") or {}
    if not isinstance(raw, dict):
        return {}
    pick = lambda *keys: next((int(raw[k]) for k in keys if isinstance(raw.get(k), (int, float))), None)  # noqa: E731
    inp = pick("input_tokens", "prompt_tokens", "promptTokenCount")
    out = pick("output_tokens", "completion_tokens", "candidatesTokenCount")
    thoughts = pick("thoughtsTokenCount")
    if out is not None and thoughts:
        out += thoughts
    counts = {"input": inp, "output": out}
    counts = {k: v for k, v in counts.items() if v is not None}
    if counts:
        counts["total"] = pick("total_tokens", "totalTokenCount") or sum(counts.values())
    return counts


def cost(model: str, counts: dict[str, int], body: dict[str, Any] | None = None) -> dict[str, float] | None:
    """USD cost: the provider's own figure when it sends one (OpenRouter), else tracing.prices
    (USD per 1M tokens) in settings.yaml; None leaves it to Langfuse's model price list."""

    reported = ((body or {}).get("usage") or {}).get("cost") if isinstance((body or {}).get("usage"), dict) else None
    if isinstance(reported, (int, float)):
        return {"total": float(reported)}
    price = (settings.get("tracing.prices") or {}).get(model)
    if not isinstance(price, dict) or not counts:
        return None
    parts = {k: counts.get(k, 0) * float(price.get(k) or 0) / 1_000_000 for k in ("input", "output")}
    parts["total"] = parts["input"] + parts["output"]
    return parts


@contextlib.contextmanager
def generation(name: str, *, model: str, provider: str, input: Any = None,
               model_parameters: dict[str, Any] | None = None, as_type: str = "generation") -> Iterator["Generation"]:
    with observe(name, as_type=as_type, model=model, input=input, metadata={"provider": provider},
                 model_parameters=model_parameters) as obs:
        yield Generation(obs, model)


class Generation:
    def __init__(self, obs: Observation, model: str) -> None:
        self.obs, self.model = obs, model

    def done(self, body: dict[str, Any] | None, output: Any = None, counts: dict[str, int] | None = None,
             **fields: Any) -> None:
        counts = counts if counts is not None else usage(body)
        self.obs.update(output=output, usage_details=counts or None,
                        cost_details=cost(self.model, counts or {}, body), **fields)


def responses_input(payload: dict[str, Any]) -> Any:
    items = payload.get("input")
    if payload.get("instructions"):
        return {"instructions": payload["instructions"], "input": items}
    return items


def responses_output(body: dict[str, Any]) -> Any:
    out: list[Any] = []
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            out.append({"tool_call": item.get("name"), "arguments": item.get("arguments")})
        for content in item.get("content") or [] if item.get("type") == "message" else []:
            out.append(content.get("text") if content.get("type") == "output_text" else content)
    return out[0] if len(out) == 1 else out
