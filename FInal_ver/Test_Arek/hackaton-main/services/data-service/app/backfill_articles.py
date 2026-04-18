from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.article_parser import extract_articles_from_text
from app.db import SessionLocal
from app.models import Article, LegalAct


def backfill_articles_from_full_text(
    limit: int = 20,
    only_missing: bool = True,
) -> dict[str, Any]:
    db = SessionLocal()

    processed = 0
    updated_acts = 0
    inserted_articles = 0
    skipped = 0
    act_ids: list[str] = []

    try:
        stmt = (
            select(LegalAct)
            .options(selectinload(LegalAct.articles))
            .where(LegalAct.full_text.is_not(None))
            .order_by(LegalAct.created_at.desc())
            .limit(limit)
        )

        acts = db.execute(stmt).scalars().all()

        for act in acts:
            processed += 1

            if only_missing and act.articles:
                skipped += 1
                continue

            extracted = extract_articles_from_text(act.full_text)
            if not extracted:
                skipped += 1
                continue

            if act.articles:
                db.execute(delete(Article).where(Article.act_id == act.id))

            for item in extracted:
                db.add(
                    Article(
                        act_id=act.id,
                        article_number=item["article_number"],
                        text=item["text"],
                    )
                )

            updated_acts += 1
            inserted_articles += len(extracted)
            act_ids.append(str(act.id))

        db.commit()

        return {
            "status": "ok",
            "processed": processed,
            "updated_acts": updated_acts,
            "inserted_articles": inserted_articles,
            "skipped": skipped,
            "act_ids": act_ids,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()