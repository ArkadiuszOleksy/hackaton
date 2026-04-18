import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

import structlog

from app.config import settings
from app.domain.models import Citation

if TYPE_CHECKING:
    from app.clients.data_service import DataServiceClient

log = structlog.get_logger()

FUZZY_THRESHOLD = 0.8

PII_PATTERNS = {
    "PESEL": re.compile(r"\b\d{11}\b"),
    "NIP": re.compile(r"\b\d{3}-\d{3}-\d{2}-\d{2}\b|\b\d{10}\b"),
    "EMAIL": re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
}


class CitationNotFoundError(ValueError):
    pass


async def validate_citations(
    citations: list[Citation],
    source_articles: list[dict[str, Any]],
    data_client: "DataServiceClient",
    request_id: str = "",
) -> list[Citation]:
    source_ids = {a.get("article_id") for a in source_articles}

    for citation in citations:
        if citation.article_id not in source_ids:
            if settings.dry_run:
                log.warning("citation.skip_m1_dry_run", article_id=citation.article_id)
                continue
            # Fallback: try M1 directly
            try:
                from app.clients.data_service import NotFoundError
                await data_client.get_legal_act(citation.article_id, request_id=request_id)
            except Exception:
                raise CitationNotFoundError(
                    f"Citation article_id='{citation.article_id}' not found in M1."
                )

    # Best-effort grounding check
    for citation in citations:
        source = next((a for a in source_articles if a.get("article_id") == citation.article_id), None)
        if source and citation.text_fragment:
            content = source.get("content", "")
            ratio = SequenceMatcher(None, citation.text_fragment.lower(), content.lower()).ratio()
            if ratio < FUZZY_THRESHOLD:
                log.warning(
                    "citation.grounding_low",
                    article_id=citation.article_id,
                    ratio=round(ratio, 3),
                )

    return citations


def mask_pii(text: str) -> str:
    for label, pattern in PII_PATTERNS.items():
        text = pattern.sub(f"[{label}_REDACTED]", text)
    return text
