import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api._common import make_error
from app.api.health import router as health_router
from app.api.analyze import router as analyze_router
from app.api.qa import router as qa_router
from app.api.summarize import router as summarize_router
from app.cache.redis_cache import RedisCache
from app.clients.data_service import DataServiceClient
from app.config import settings
from app.llm.openrouter import OpenRouterClient


def _configure_logging() -> None:
    processors = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.environment == "dev":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


_configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    http_client = httpx.AsyncClient()
    app.state.redis_cache = RedisCache(settings.redis_url)
    app.state.openrouter = OpenRouterClient(http_client)
    app.state.data_client = DataServiceClient(http_client)
    app.state.settings = settings
    log.info("startup", service="ai-service", environment=settings.environment)
    yield
    await http_client.aclose()
    log.info("shutdown", service="ai-service")


app = FastAPI(
    title="ai-service",
    version="0.1.0",
    description="CivicLens M2 — LLM/RAG service",
    docs_url="/docs" if settings.environment != "prod" else None,
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(health_router)
app.include_router(qa_router)
app.include_router(analyze_router)
app.include_router(summarize_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    log.error("unhandled_exception", request_id=request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=make_error("INTERNAL_ERROR", "An unexpected error occurred.", request_id),
    )
