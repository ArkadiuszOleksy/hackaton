from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.clients_sejm_eli import SejmEliClient
from app.db import SessionLocal
from app.models import LegalAct
from app.text_utils import fix_mojibake


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value + "T00:00:00+00:00")
    except ValueError:
        return None


def _to_sejm_id(details: dict[str, Any], fallback_publisher: str, fallback_year: int, fallback_pos: int) -> str:
    if details.get("ELI"):
        return str(details["ELI"])
    if details.get("address"):
        return str(details["address"])
    return f"{fallback_publisher}/{fallback_year}/{fallback_pos}"


def run_eli_import(
    publisher: str = "DU",
    year: int = 2026,
    limit: int = 5,
    with_text: bool = False,
) -> dict[str, Any]:
    client = SejmEliClient()
    db = SessionLocal()

    imported = 0
    updated = 0
    skipped = 0
    text_saved = 0
    processed_positions: list[int] = []

    try:
        acts = client.get_acts_in_year(publisher=publisher, year=year)
        acts = acts[:limit]

        for item in acts:
            position = int(item["pos"])
            processed_positions.append(position)

            details = client.get_act_details(publisher=publisher, year=year, position=position)
            sejm_id = _to_sejm_id(details, publisher, year, position)

            existing = db.execute(
                select(LegalAct).where(LegalAct.sejm_id == sejm_id)
            ).scalar_one_or_none()

            full_text: str | None = None
            if with_text:
                try:
                    full_text = client.get_act_html_text(
                        publisher=publisher,
                        year=year,
                        position=position,
                    )
                except Exception:
                    full_text = None

            payload = {
                "sejm_id": sejm_id,
                "title": fix_mojibake(details.get("title") or item.get("title") or f"{publisher}/{year}/{position}"),
                "status": fix_mojibake(details.get("status") or item.get("status")),
                "kadencja": None,
                "published_at": _parse_datetime(details.get("promulgation") or details.get("announcementDate")),
                "source_url": f"https://api.sejm.gov.pl/eli/acts/{publisher}/{year}/{position}",
                "full_text": fix_mojibake(full_text),
            }

            if payload["full_text"]:
                text_saved += 1

            if existing is None:
                act = LegalAct(**payload)
                db.add(act)
                imported += 1
            else:
                existing.title = payload["title"]
                existing.status = payload["status"]
                existing.published_at = payload["published_at"]
                existing.source_url = payload["source_url"]
                if payload["full_text"]:
                    existing.full_text = payload["full_text"]
                updated += 1

        db.commit()

        return {
            "status": "ok",
            "publisher": publisher,
            "year": year,
            "limit": limit,
            "with_text": with_text,
            "processed": len(processed_positions),
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "positions": processed_positions,
            "text_saved": text_saved,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()