from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Patent
from app.schemas import PatentSearchResponse
from app.search_utils import score_text_match

router = APIRouter(tags=["patents"])


@router.get("/patents", response_model=PatentSearchResponse)
def search_patents(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    patents = db.execute(select(Patent)).scalars().all()

    scored = []
    for patent in patents:
        haystack = " ".join(
            [
                patent.uprp_id or "",
                patent.title or "",
                patent.abstract or "",
            ]
        )
        score = score_text_match(q, haystack)

        if score > 0:
            scored.append(
                {
                    "id": patent.id,
                    "uprp_id": patent.uprp_id,
                    "title": patent.title,
                    "abstract": patent.abstract,
                    "source_url": patent.source_url,
                    "filed_at": patent.filed_at,
                    "score": score,
                }
            )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["filed_at"] or "",
        ),
        reverse=True,
    )

    return {"data": scored[:top_k]}