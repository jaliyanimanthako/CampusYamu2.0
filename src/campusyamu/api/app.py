"""CampusYamu public API (FastAPI), separate from the web front end.

One HTTP API for every client (the web app, the mobile app, anything else).
Interactive docs: /docs  ·  OpenAPI spec: /openapi.json

    uv run python -m campusyamu.api                 # http://127.0.0.1:8780/docs
    uv run python -m campusyamu.api --host 0.0.0.0 --port 8780

GET  /v1/health                   liveness + whether OpenAI is configured
GET  /v1/options                  form values: streams, subjects, grades, districts, DS divisions
GET  /v1/courses                  every course name (for the career-outlook endpoints)
POST /v1/recommendations          run the student pipeline; returns the report
POST /v1/chat                     one question about one course from the report
GET  /v1/career-outlook?course=   cached career outlook + background research status
POST /v1/career-outlook/research  start career research for one course (runs for minutes; poll the GET)

Errors always look like {"errors": ["..."]}. If CAMPUSYAMU_API_KEY is set, every
/v1 endpoint except /v1/health needs the header `X-API-Key: <key>`.
"""

from __future__ import annotations

import asyncio
import hmac
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
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException

from campusyamu.core import settings

from . import schemas as s

try:
    VERSION = version("campusyamu")
except PackageNotFoundError:  # running from a source checkout without install
    VERSION = "0.0.0"

ERRORS = {code: {"model": s.ErrorResponse} for code in (400, 401, 409, 422, 500, 502)}
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _default_service():
    from .service import AdvisorService  # heavy import: graph, SQLite, Neo4j clients

    return AdvisorService()


def cors_origins() -> list[str]:
    env = os.getenv("API_CORS_ORIGINS")
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return list(settings.get("api.cors_origins", ["*"]))


def require_api_key(key: str | None = Depends(_api_key_header)) -> None:
    expected = os.getenv("CAMPUSYAMU_API_KEY")
    if expected and not (key and hmac.compare_digest(key, expected)):
        raise StarletteHTTPException(401, "Missing or invalid X-API-Key")


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


def create_app(service_factory: Callable[[], Any] | None = None) -> FastAPI:
    service = Service(service_factory or _default_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    app = FastAPI(
        title="CampusYamu API",
        version=VERSION,
        summary="Course recommendations, course chat and career outlooks for Sri Lankan state universities "
                "(UGC 2024/2025 handbook).",
        lifespan=lifespan,
        responses=ERRORS,
    )
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Content-Type", "X-API-Key"])

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
    v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])

    @public.get("/health", response_model=s.Health)
    async def health() -> dict[str, Any]:
        web = service.app
        return {"ok": web is not None, "version": VERSION,
                "llm_available": bool(web and web.options.get("llm_available"))}

    @v1.get("/options", response_model=s.Options, tags=["form"])
    async def options() -> dict[str, Any]:
        """Values for the student form. Load once at app start."""
        return service.app.options

    @v1.get("/courses", response_model=list[str], tags=["form"])
    async def courses() -> list[str]:
        return sorted(service.app.course_names)

    @v1.post("/recommendations", response_model=s.RecommendationResponse, tags=["recommendations"])
    async def recommendations(body: s.RecommendationRequest, response: Response) -> Any:
        """Eligible courses in bands plus ranked suggestions. Takes ~1 s, or 20–40 s with `use_llm`."""
        status, data = await service.call(service.app.run, body.model_dump())
        return _reply(response, status, data)

    @v1.post("/chat", response_model=s.ChatResponse, tags=["chat"])
    async def chat(body: s.ChatRequest, response: Response) -> Any:
        """Answer one question about one course, from the handbook and the student's results.

        Send `course` as the course row from the recommendations report and the earlier turns in
        `history`. If `career.job.state` is `running` in the reply, poll GET /v1/career-outlook.
        """
        status, data = await service.call(service.app.ask, body.model_dump())
        return _reply(response, status, data)

    @v1.get("/career-outlook", response_model=s.CareerStatus, tags=["career"])
    async def career_outlook(course: str = Query(min_length=1, examples=["Quantity Surveying"])) -> Any:
        """Cached career outlook and research-job status for one course. Poll every few seconds while running."""
        return await service.call(service.app.career, course)

    @v1.post("/career-outlook/research", response_model=s.CareerResearchResponse, status_code=202,
             tags=["career"])
    async def career_research(body: s.CareerResearchRequest, response: Response) -> Any:
        """Start web research for one course in the background (paid; minutes). 409 if another is running."""
        status, data = await service.call(service.app.start_career, body.model_dump())
        return _reply(response, status, data)

    app.include_router(public)
    app.include_router(v1)
    return app
