from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.error_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.request_id import RequestIdMiddleware
from app.routers.admin import router as admin_router
from app.routers.articles import router as articles_router
from app.routers.health import router as health_router
from app.routers.legal_acts import router as legal_acts_router
from app.routers.patents import router as patents_router
from app.routers.trends import router as trends_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(RequestIdMiddleware)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(legal_acts_router)
app.include_router(articles_router)
app.include_router(patents_router)
app.include_router(admin_router)
app.include_router(trends_router)