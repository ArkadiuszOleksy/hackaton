from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Article, LegalAct
from app.schemas import ArticleSearchResponse

router = APIRouter(tags=["articles"])


@router.get("/articles/search", response_model=ArticleSearchResponse)
def search_articles(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=8, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    tokens = [token.strip() for token in q.split() if token.strip()]

    if not tokens:
        return {"data": []}

    conditions = []
    score_parts = []

    for token in tokens:
        pattern = f"%{token}%"
        token_match = or_(
            Article.text.ilike(pattern),
            Article.article_number.ilike(pattern),
            LegalAct.title.ilike(pattern),
        )
        conditions.append(token_match)
        score_parts.append(case((token_match, 1), else_=0))

    score_expr = sum(score_parts).label("score")

    stmt = (
        select(
            Article.id,
            Article.act_id,
            LegalAct.title.label("act_title"),
            Article.article_number,
            Article.text,
            score_expr,
        )
        .join(LegalAct, LegalAct.id == Article.act_id)
        .where(or_(*conditions))
        .order_by(desc("score"), Article.article_number.asc())
        .limit(top_k)
    )

    rows = db.execute(stmt).all()

    data = [
        {
            "id": row.id,
            "act_id": row.act_id,
            "act_title": row.act_title,
            "article_number": row.article_number,
            "text": row.text,
            "score": int(row.score or 0),
        }
        for row in rows
    ]

    return {"data": data}

@router.get("/legal-acts/{act_id}/articles", response_model=ArticleSearchResponse)
def get_act_articles(
    act_id: str,
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(
            Article.id,
            Article.act_id,
            LegalAct.title.label("act_title"),
            Article.article_number,
            Article.text,
        )
        .join(LegalAct, LegalAct.id == Article.act_id)
        .where(Article.act_id == act_id)
        .order_by(Article.article_number.asc())
    )

    rows = db.execute(stmt).all()

    data = [
        {
            "id": str(row.id),
            "act_id": str(row.act_id),
            "act_title": row.act_title,
            "article_number": row.article_number,
            "text": row.text,
            "score": 1,
        }
        for row in rows
    ]

    return {"data": data}
