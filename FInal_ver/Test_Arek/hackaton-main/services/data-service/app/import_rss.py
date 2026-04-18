from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import NewsItem


RSS_SOURCES: list[dict[str, str]] = [
    {"name": "Bankier - Firma", "url": "https://www.bankier.pl/rss/firma.xml"},
    {"name": "UOKiK", "url": "https://uokik.gov.pl/feed"},
]

DEMO_FALLBACK_ITEMS: list[dict[str, Any]] = [
    {
        "source_name": "DEMO",
        "title": "Projekt ustawy o uproszczeniu obowiązków sprawozdawczych przedsiębiorców",
        "link": "https://demo.local/news/1",
        "summary": "Przykładowy wpis trendowy do działania dashboardu i testów integracyjnych.",
        "published_at": datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc),
    },
    {
        "source_name": "DEMO",
        "title": "Nowe propozycje zmian w podatkach dla MŚP",
        "link": "https://demo.local/news/2",
        "summary": "Przykładowy wpis pokazujący sygnały legislacyjne istotne dla małych firm.",
        "published_at": datetime(2026, 4, 18, 12, 5, 0, tzinfo=timezone.utc),
    },
    {
        "source_name": "DEMO",
        "title": "Dyskusja publiczna wokół zmian w prawie gospodarczym",
        "link": "https://demo.local/news/3",
        "summary": "Fallback demo, gdy zewnętrzne RSS-y są chwilowo niedostępne.",
        "published_at": datetime(2026, 4, 18, 12, 10, 0, tzinfo=timezone.utc),
    },
]


def _parse_rss_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _text_of(parent: ET.Element, tag_names: list[str]) -> str | None:
    for child in list(parent):
        local = child.tag.split("}")[-1].lower()
        if local in tag_names:
            text = (child.text or "").strip()
            if text:
                return text
    return None


def _parse_items(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []

    for elem in root.iter():
        local = elem.tag.split("}")[-1].lower()
        if local != "item":
            continue

        title = _text_of(elem, ["title"])
        link = _text_of(elem, ["link"])
        summary = _text_of(elem, ["description", "summary"])
        published_raw = _text_of(elem, ["pubdate", "published", "updated"])

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": _parse_rss_datetime(published_raw),
            }
        )

    return items


def _insert_news_item(
    db,
    *,
    source_name: str,
    title: str,
    link: str,
    summary: str | None,
    published_at: datetime | None,
) -> bool:
    existing = db.execute(
        select(NewsItem).where(NewsItem.link == link)
    ).scalar_one_or_none()

    if existing is not None:
        return False

    news = NewsItem(
        source_name=source_name,
        title=title,
        link=link,
        summary=summary,
        published_at=published_at,
    )
    db.add(news)
    return True


def run_rss_import(limit_per_source: int = 10) -> dict[str, Any]:
    db = SessionLocal()
    imported = 0
    skipped = 0
    errors = 0
    per_source: list[dict[str, Any]] = []

    try:
        with httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 CivicLens/0.1 RSS importer",
                "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            },
        ) as client:
            for source in RSS_SOURCES:
                source_name = source["name"]
                source_url = source["url"]

                try:
                    response = client.get(source_url)
                    response.raise_for_status()

                    parsed_items = _parse_items(response.text)[:limit_per_source]
                    source_imported = 0
                    source_skipped = 0

                    for item in parsed_items:
                        was_inserted = _insert_news_item(
                            db,
                            source_name=source_name,
                            title=item["title"],
                            link=item["link"],
                            summary=item["summary"],
                            published_at=item["published_at"],
                        )
                        if was_inserted:
                            source_imported += 1
                            imported += 1
                        else:
                            source_skipped += 1
                            skipped += 1

                    per_source.append(
                        {
                            "source_name": source_name,
                            "source_url": source_url,
                            "fetched": len(parsed_items),
                            "imported": source_imported,
                            "skipped": source_skipped,
                            "error": None,
                        }
                    )
                except Exception as exc:
                    errors += 1
                    per_source.append(
                        {
                            "source_name": source_name,
                            "source_url": source_url,
                            "fetched": 0,
                            "imported": 0,
                            "skipped": 0,
                            "error": str(exc),
                        }
                    )

        # fallback demo, jeśli nic realnego nie weszło
        fallback_inserted = 0
        if imported == 0:
            for item in DEMO_FALLBACK_ITEMS:
                was_inserted = _insert_news_item(
                    db,
                    source_name=item["source_name"],
                    title=item["title"],
                    link=item["link"],
                    summary=item["summary"],
                    published_at=item["published_at"],
                )
                if was_inserted:
                    fallback_inserted += 1
                    imported += 1
                else:
                    skipped += 1

            per_source.append(
                {
                    "source_name": "DEMO_FALLBACK",
                    "source_url": "local",
                    "fetched": len(DEMO_FALLBACK_ITEMS),
                    "imported": fallback_inserted,
                    "skipped": len(DEMO_FALLBACK_ITEMS) - fallback_inserted,
                    "error": None,
                }
            )

        db.commit()

        return {
            "status": "ok",
            "sources": per_source,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()