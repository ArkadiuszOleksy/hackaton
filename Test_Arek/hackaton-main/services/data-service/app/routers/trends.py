from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import NewsItem
from app.schemas import NewsSourcesResponse

router = APIRouter(tags=["trends"])


@router.get("/trends/sources", response_model=NewsSourcesResponse)
def list_trend_sources(
    limit: int = Query(default=50, ge=1, le=100),
    source_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(NewsItem).order_by(
        NewsItem.published_at.desc().nullslast(),
        NewsItem.created_at.desc(),
    )

    if source_name:
        stmt = stmt.where(NewsItem.source_name == source_name)

    stmt = stmt.limit(limit)

    items = db.execute(stmt).scalars().all()
    return {"data": items}