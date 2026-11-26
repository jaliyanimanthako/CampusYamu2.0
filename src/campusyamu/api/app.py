"""CampusYamu public API (FastAPI), separate from the web front end.

One HTTP API for every client (the web app, the mobile app, anything else).
Interactive docs: /docs  ·  OpenAPI spec: /openapi.json

    uv run python -m campusyamu.api                 # http://127.0.0.1:8780/docs
    uv run python -m campusyamu.api --host 0.0.0.0 --port 8780

GET  /v1/health                   liveness + whether the language model (llm.provider) is configured
GET  /v1/options                  form values: streams, subjects, grades, districts, towns
GET  /v1/courses                  every course name (for the career-outlook endpoints)
POST /v1/recommendations          run the student pipeline; returns the report
POST /v1/recommendations/stream   the same, as server-sent events: each pipeline step as it finishes, then the report
POST /v1/chat/stream              /v1/chat as server-sent events: the answer's text as it is written, then the result
POST /v1/chat                     one question about one course from the report
GET  /v1/career-outlook?course=   cached career outlook + background research status
POST /v1/career-outlook/research  start career research for one course (runs for minutes; poll the GET)
GET  /v1/me                       the signed-in student: name for greetings, today's use of the paid calls
GET  /v1/me/results               their latest search: the form and the report (saved by /recommendations)
GET  /v1/me/chats                 their course chats (newest first)
GET  /v1/me/chats/{uni_code}      one chat's messages (paged with ?before=)
DELETE /v1/me/chats/{uni_code}    delete one chat (its messages and summary)

Errors always look like {"errors": ["..."]}. When SUPABASE_URL is set, every /v1
endpoint except /v1/health needs `Authorization: Bearer <Supabase access token>` of a
signed-in student (api/auth.py); /v1/chat then keeps that student's chat memory.
"""

from __future__ import annotations

import asyncio
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException as StarletteHTTPException

from campusyamu.core import settings, tracing

from . import schemas as s
from .auth import AccountExistsError, AuthError, LocalAuthStore, SupabaseAuth

try:
    VERSION = version("campusyamu")
except PackageNotFoundError:  # running from a source checkout without install
    VERSION = "0.0.0"

ERRORS = {code: {"model": s.ErrorResponse} for code in (400, 401, 404, 409, 422, 429, 500, 502)}
_bearer = HTTPBearer(auto_error=False, description="Supabase access token of the signed-in student")


def _default_service():
    from .service import AdvisorService  # heavy import: graph, SQLite, Neo4j clients

    return AdvisorService()


def cors_origins() -> list[str]:
    env = os.getenv("API_CORS_ORIGINS")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return list(settings.get("api.cors_origins", ["*"]))


def current_user(request: Request,
                 credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str | None:
    """The signed-in student's id; None when sign-in is off and no local token was sent."""

    auth: SupabaseAuth = request.app.state.auth
    if not auth.enabled:
        if credentials is None:
            return None
        local_auth: LocalAuthStore = request.app.state.local_auth
        try:
            return local_auth.user_id(credentials.credentials)
        except AuthError as exc:
            raise StarletteHTTPException(401, str(exc)) from exc
    if credentials is None:
        raise StarletteHTTPException(401, "Sign in first: send Authorization: Bearer <Supabase access token>")
    try:
        return auth.user_id(credentials.credentials)
    except AuthError as exc:
        raise StarletteHTTPException(401, str(exc)) from exc


def current_profile(request: Request,
                    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict[str, str | None]:
    """The signed-in student's name from the verified token (display_name, first_name); None values if absent."""

    empty: dict[str, str | None] = {"display_name": None, "first_name": None}
    if credentials is None:
        return empty
    auth: SupabaseAuth = request.app.state.auth
    source: Any = auth if auth.enabled else request.app.state.local_auth
    try:
        return source.profile(credentials.credentials)
    except AuthError:
        return empty            # current_user has already rejected a bad token


def signed_in_user(user: str | None = Depends(current_user)) -> str:
    """For /v1/me...: these need sign-in even on a development server without it."""

    if user is None:
        raise StarletteHTTPException(400, "Sign-in is off on this server (no SUPABASE_URL), so there is no account")
    return user


class Service:
    """Runs every call on one worker thread: the pipeline's SQLite connections are bound to it."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self.factory = factory
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="campusyamu-api")
        self.app: Any = None

    async def call(self, fn: Callable[..., Any], *args: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(self.executor, partial(fn, *args))

    async def start(self) -> None:
        self.app = await self.call(self.factory)

    async def stop(self) -> None:
        if self.app is not None:
            def close() -> None:
                for part in (getattr(self.app, "finder", None), getattr(self.app, "chat", None)):
                    if part is not None and hasattr(part, "close"):
                        part.close()
            await self.call(close)
        self.executor.shutdown(wait=False)


def _reply(response: Response, status: int, data: dict[str, Any]) -> Any:
    if status >= 400:
        return JSONResponse(status_code=status, content=data)
    response.status_code = status
    return data


def create_app(service_factory: Callable[[], Any] | None = None, auth: SupabaseAuth | None = None) -> FastAPI:
    service = Service(service_factory or _default_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await service.start()
        try:
            yield
        finally:
            await service.stop()
            tracing.flush()                             # send buffered Langfuse traces

    app = FastAPI(
        title="CampusYamu API",
        version=VERSION,
        summary="Course recommendations, course chat and career outlooks for Sri Lankan state universities "
                "(UGC 2024/2025 handbook).",
        lifespan=lifespan,
        responses=ERRORS,
    )
    app.state.service = service
    app.state.auth = auth or SupabaseAuth()
    app.state.local_auth = LocalAuthStore()
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                       allow_headers=["Content-Type", "Authorization"])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"errors": [str(exc.detail)]})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query"))
            errors.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
        return JSONResponse(status_code=422, content={"errors": errors})

    @app.exception_handler(Exception)
    async def server_error(_: Request, exc: Exception) -> JSONResponse:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"errors": [f"Request failed: {exc}"]})

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    public = APIRouter(prefix="/v1", tags=["meta"])
    v1 = APIRouter(prefix="/v1", dependencies=[Depends(current_user)])

    @public.get("/health", response_model=s.Health)
    async def health() -> dict[str, Any]:
        web = service.app
        return {"ok": web is not None, "version": VERSION,
                "llm_available": bool(web and web.options.get("llm_available"))}

    @public.post("/auth/signup", response_model=s.AuthResponse, status_code=201, tags=["auth"])
    async def auth_signup(body: s.SignUpRequest) -> dict[str, Any]:
        """Create a local student account (when Supabase Auth is not configured)."""
        try:
            return app.state.local_auth.signup(body.email, body.password, body.name, body.avatar)
        except AccountExistsError as exc:
            raise StarletteHTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise StarletteHTTPException(422, str(exc)) from exc

    @public.post("/auth/signin", response_model=s.AuthResponse, tags=["auth"])
    async def auth_signin(body: s.SignInRequest) -> dict[str, Any]:
        """Sign in with a local student account (when Supabase Auth is not configured)."""
        try:
            return app.state.local_auth.signin(body.email, body.password)
        except AuthError as exc:
            raise StarletteHTTPException(401, str(exc)) from exc

    @v1.post("/auth/avatar", response_model=s.AuthUser, tags=["auth"])
    async def auth_set_avatar(body: s.SetAvatarRequest, user: str = Depends(signed_in_user)) -> dict[str, Any]:
        """Set the local student's avatar once after account creation."""
        try:
            return app.state.local_auth.set_avatar(user, body.avatar)
        except AccountExistsError as exc:
            raise StarletteHTTPException(409, str(exc)) from exc
        except AuthError as exc:
            raise StarletteHTTPException(401, str(exc)) from exc

    @v1.get("/options", response_model=s.Options, tags=["form"])
    async def options() -> dict[str, Any]:
        """Values for the student form. Load once at app start."""
        return service.app.options

    @v1.get("/courses", response_model=list[str], tags=["form"])
    async def courses() -> list[str]:
        return sorted(service.app.course_names)

    @v1.post("/recommendations", response_model=s.RecommendationResponse, tags=["recommendations"])
    async def recommendations(body: s.RecommendationRequest, response: Response,
                              user: str | None = Depends(current_user)) -> Any:
        """Eligible courses in bands plus ranked suggestions. Takes ~1 s, or 20–40 s with `use_llm`."""
        status, data = await service.call(service.app.run, body.model_dump(), user)
        return _reply(response, status, data)

    def sse_response(work: Callable[[Callable[[str, dict[str, Any]], None]], Any]) -> StreamingResponse:
        """Run `work(send)` on the worker thread; every send(event, data) becomes one server-sent event,
        and the (status, data) it returns becomes the final `result` event: data plus `http_status`
        (a separate field, since the chat result has its own `status`)."""

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

        def send(kind: str, data: dict[str, Any]) -> None:          # called on the worker thread
            loop.call_soon_threadsafe(queue.put_nowait, (kind, data))

        async def run() -> None:
            try:
                status, data = await service.call(work, send)
                result = {**data, "http_status": status}
            except Exception as exc:                              # report it in the stream; keep the server up
                traceback.print_exc()
                result = {"http_status": 500, "errors": [f"Request failed: {exc}"]}
            await queue.put(("result", result))

        task = asyncio.create_task(run())

        async def events():
            # If the client disconnects, the work still finishes on the worker thread (results are saved).
            while True:
                kind, data = await queue.get()
                yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
                if kind == "result":
                    break
            await task

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @v1.post("/recommendations/stream", tags=["recommendations"], response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Server-sent events: `progress` per finished step, then one `result`"}})
    async def recommendations_stream(body: s.RecommendationRequest,
                                     user: str | None = Depends(current_user)) -> StreamingResponse:
        """POST /v1/recommendations with live progress, for the analysing screen. Same input, limits and saving.

        The response is `text/event-stream`:

            event: progress
            data: {"step": "eligibility", "status": "done", "courses_checked": 126, "eligible": 55}

        `step` is eligibility, travel, zscore, interests or ranking; `status` is running, done or skipped
        (zscore also sends `done` and `total` courses). It ends with exactly one

            event: result
            data: {"http_status": 200, "report": {...}, "used_llm": false}  (or {"http_status": 400, "errors": [...]})
        """
        form = body.model_dump()
        return sse_response(lambda send: service.app.run(form, user, lambda event: send("progress", event)))

    @v1.post("/chat", response_model=s.ChatResponse, tags=["chat"])
    async def chat(body: s.ChatRequest, response: Response, user: str | None = Depends(current_user)) -> Any:
        """Answer one question about one course, from the handbook and the student's results.

        Send `course` as the course row from the recommendations report. Signed in, the server keeps
        the chat (memory per student and course) and `history` is ignored; with sign-in off, send the
        earlier turns in `history`. If `career.job.state` is `running`, poll GET /v1/career-outlook.
        """
        status, data = await service.call(service.app.ask, body.model_dump(), user)
        return _reply(response, status, data)

    @v1.post("/chat/stream", tags=["chat"], response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Server-sent events: `token` pieces of the answer, then one `result`"}})
    async def chat_stream(body: s.ChatRequest, user: str | None = Depends(current_user)) -> StreamingResponse:
        """POST /v1/chat, with the answer streamed as it is written. Same input, limits, memory and result.

        The response is `text/event-stream`:

            event: token
            data: {"text": "Yes, Architecture at Moratuwa needs an aptitude test [S1]"}

        (append each `text` in order), then exactly one

            event: result
            data: {"http_status": 200, "answer": "...", "status": "answered", "sources": [...], ...}

        with the same fields as POST /v1/chat plus `http_status` (or {"http_status": 4xx, "errors": [...]}). Use `result.answer` as
        the final text. A message outside the chat's scope gets its refusal in the result with no tokens.
        """
        payload = body.model_dump()
        return sse_response(lambda send: service.app.ask(payload, user, lambda text: send("token", {"text": text})))

    @v1.get("/career-outlook", response_model=s.CareerStatus, tags=["career"])
    async def career_outlook(course: str = Query(min_length=1, examples=["Quantity Surveying"])) -> Any:
        """Cached career outlook and research-job status for one course. Poll every few seconds while running."""
        return await service.call(service.app.career, course)

    @v1.post("/career-outlook/research", response_model=s.CareerResearchResponse, status_code=202,
             tags=["career"])
    async def career_research(body: s.CareerResearchRequest, response: Response,
                              user: str | None = Depends(current_user)) -> Any:
        """Start web research for one course in the background (paid; minutes). 409 if another is running."""
        status, data = await service.call(service.app.start_career, body.model_dump(), user)
        return _reply(response, status, data)

    @v1.get("/me", response_model=s.Me, tags=["account"])
    async def me(user: str = Depends(signed_in_user),
                 profile: dict[str, str | None] = Depends(current_profile)) -> Any:
        """The signed-in student: their name for greetings (first_name is the first word of display_name, e.g.
        "Jaliya" from "Jaliya Nimantha"; null when the sign-in has no name) and today's use of the paid calls
        (limits reset at midnight, Sri Lanka time)."""
        return {**await service.call(service.app.me, user), **profile}

    @v1.get("/me/results", response_model=s.SavedResults, tags=["account"])
    async def my_results(response: Response, user: str = Depends(signed_in_user)) -> Any:
        """The student's latest search (saved by POST /v1/recommendations): fill the form and show the report
        again after a reload or on another device. 404 before the first search."""
        status, data = await service.call(service.app.results, user)
        return _reply(response, status, data)

    @v1.get("/me/chats", response_model=list[s.ChatSummary], tags=["account"])
    async def my_chats(user: str = Depends(signed_in_user)) -> Any:
        """The student's course chats, most recent first. Open one with GET /v1/me/chats/{uni_code}."""
        return await service.call(service.app.chats, user)

    @v1.get("/me/chats/{uni_code}", response_model=s.ChatHistory, tags=["account"])
    async def my_chat(uni_code: str, response: Response, user: str = Depends(signed_in_user),
                      before: int | None = Query(None, ge=1, description="Only messages with a smaller seq"),
                      limit: int = Query(50, ge=1, le=200)) -> Any:
        """One course chat's saved messages (newest `limit`, oldest first): show them when the chat opens."""
        status, data = await service.call(service.app.chat_history, user, uni_code, before, limit)
        return _reply(response, status, data)

    @v1.delete("/me/chats/{uni_code}", response_model=s.Deleted, tags=["account"])
    async def delete_my_chat(uni_code: str, response: Response, user: str = Depends(signed_in_user)) -> Any:
        """Delete one course chat for good: its messages and summary. Student facts stay."""
        status, data = await service.call(service.app.delete_chat, user, uni_code)
        return _reply(response, status, data)

    app.include_router(public)
    app.include_router(v1)
    return app
