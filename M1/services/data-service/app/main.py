from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings
from app.routers.health import router as health_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.include_router(health_router)