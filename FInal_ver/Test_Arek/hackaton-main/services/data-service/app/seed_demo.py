from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Article, LegalAct


def run_seed() -> dict:
    db = SessionLocal()
    try:
        existing = db.execute(
            select(LegalAct).where(LegalAct.sejm_id == "demo-10-druk-123")
        ).scalar_one_or_none()

        if existing is not None:
            return {
                "status": "ok",
                "inserted": False,
                "message": "Seed already exists, skipping.",
                "legal_act_id": str(existing.id),
            }

        act = LegalAct(
            sejm_id="demo-10-druk-123",
            title="Ustawa o zmianie ustawy o podatku od towarów i usług",
            status="przyjety",
            kadencja=10,
            published_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
            source_url="https://api.sejm.gov.pl/",
            full_text=(
                "Art. 1. Wprowadza się zmianę definicji usługi gastronomicznej.\n"
                "Art. 2. Ustala się obowiązek raportowania kwartalnego.\n"
                "Art. 3. Stawka VAT na wybrane usługi gastronomiczne wynosi 23%."
            ),
        )

        db.add(act)
        db.flush()

        articles = [
            Article(
                act_id=act.id,
                article_number="Art. 1",
                text="Wprowadza się zmianę definicji usługi gastronomicznej.",
            ),
            Article(
                act_id=act.id,
                article_number="Art. 2",
                text="Ustala się obowiązek raportowania kwartalnego dla przedsiębiorców objętych ustawą.",
            ),
            Article(
                act_id=act.id,
                article_number="Art. 3",
                text="Stawka podatku VAT na wybrane usługi gastronomiczne wynosi 23%.",
            ),
        ]

        db.add_all(articles)
        db.commit()

        return {
            "status": "ok",
            "inserted": True,
            "message": "Seed inserted.",
            "legal_act_id": str(act.id),
            "articles_inserted": len(articles),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    result = run_seed()
    print(result)