from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.backfill_articles import backfill_articles_from_full_text
from app.import_rss import run_rss_import
from app.import_sejm_eli import run_eli_import
from app.schemas import (
    ArticlesBackfillResponse,
    EliImportResponse,
    EtlRunResponse,
    PatentSeedResponse,
    RssImportResponse,
)
from app.seed_demo import run_seed
from app.seed_patents_demo import run_patents_seed

router = APIRouter(tags=["admin"])


@router.post("/admin/etl/run", response_model=EtlRunResponse)
def run_etl() -> dict:
    try:
        result = run_seed()
        return {"data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ETL run failed: {exc}",
        ) from exc


@router.post("/admin/import/eli", response_model=EliImportResponse)
def import_from_eli(
    publisher: str = Query(default="DU"),
    year: int = Query(default=2026, ge=1900, le=2100),
    limit: int = Query(default=5, ge=1, le=50),
    with_text: bool = Query(default=False),
) -> dict:
    try:
        result = run_eli_import(
            publisher=publisher,
            year=year,
            limit=limit,
            with_text=with_text,
        )
        return {"data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ELI import failed: {exc}",
        ) from exc


@router.post("/admin/import/rss", response_model=RssImportResponse)
def import_rss(
    limit_per_source: int = Query(default=10, ge=1, le=50),
) -> dict:
    try:
        result = run_rss_import(limit_per_source=limit_per_source)
        return {"data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RSS import failed: {exc}",
        ) from exc


@router.post("/admin/backfill/articles", response_model=ArticlesBackfillResponse)
def backfill_articles(
    limit: int = Query(default=20, ge=1, le=100),
    only_missing: bool = Query(default=True),
) -> dict:
    try:
        result = backfill_articles_from_full_text(
            limit=limit,
            only_missing=only_missing,
        )
        return {"data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Articles backfill failed: {exc}",
        ) from exc


@router.post("/admin/seed/patents", response_model=PatentSeedResponse)
def seed_patents() -> dict:
    try:
        result = run_patents_seed()
        return {"data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patent seed failed: {exc}",
        ) from exc