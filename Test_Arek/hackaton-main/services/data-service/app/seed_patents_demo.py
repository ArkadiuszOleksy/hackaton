from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Patent


DEMO_PATENTS = [
    {
        "uprp_id": "DEMO-PAT-001",
        "title": "System monitorowania zużycia energii w małych przedsiębiorstwach",
        "abstract": "Rozwiązanie do analizy zużycia energii, prognozowania kosztów i generowania rekomendacji oszczędnościowych dla MŚP.",
        "source_url": "https://demo.local/patents/1",
        "filed_at": datetime(2025, 6, 10, 10, 0, 0, tzinfo=timezone.utc),
    },
    {
        "uprp_id": "DEMO-PAT-002",
        "title": "Modułowa platforma do finansowania społecznościowego projektów lokalnych",
        "abstract": "Platforma wspierająca crowdfinancing i raportowanie projektów lokalnych z mechanizmami zgodności regulacyjnej.",
        "source_url": "https://demo.local/patents/2",
        "filed_at": datetime(2025, 7, 2, 10, 0, 0, tzinfo=timezone.utc),
    },
    {
        "uprp_id": "DEMO-PAT-003",
        "title": "Panel solarny z adaptacyjnym sterowaniem wydajnością",
        "abstract": "Układ sterowania pracą paneli solarnych dopasowujący parametry pracy do zmiennych warunków nasłonecznienia.",
        "source_url": "https://demo.local/patents/3",
        "filed_at": datetime(2025, 8, 18, 10, 0, 0, tzinfo=timezone.utc),
    },
]


def run_patents_seed() -> dict:
    db = SessionLocal()
    inserted = 0
    skipped = 0

    try:
        for item in DEMO_PATENTS:
            existing = db.execute(
                select(Patent).where(Patent.uprp_id == item["uprp_id"])
            ).scalar_one_or_none()

            if existing is not None:
                skipped += 1
                continue

            db.add(Patent(**item))
            inserted += 1

        db.commit()

        return {
            "status": "ok",
            "inserted": inserted,
            "skipped": skipped,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print(run_patents_seed())