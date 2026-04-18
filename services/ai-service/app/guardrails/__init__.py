from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from app.domain.models import Citation
from app.domain.rules import DISCLAIMER_TEXT, ensure_disclaimer
from app.guardrails.citations import CitationNotFoundError, mask_pii, validate_citations
from app.guardrails.schema import SchemaValidationError, validate_llm_output

T = TypeVar("T", bound=BaseModel)


async def run_guardrails(
    raw: str,
    schema: type[T],
    source_articles: list[dict[str, Any]],
    data_client: Any,
    request_id: str,
    retry_fn: Callable[[str], Awaitable[str]] | None = None,
    require_citations: bool = True,
) -> T:
    if retry_fn is None:
        async def _no_retry(msg: str) -> str:
            raise SchemaValidationError(f"No retry function provided: {msg}")
        retry_fn = _no_retry

    # Steps 1+2: JSON parse + Pydantic validate
    validated = await validate_llm_output(raw, schema, retry_fn)

    # Steps 3+4: Citation existence + grounding
    if require_citations and hasattr(validated, "citations"):
        citations: list[Citation] = validated.citations  # type: ignore[assignment]
        if not citations:
            raise CitationNotFoundError("Response contains no citations.")
        await validate_citations(citations, source_articles, data_client, request_id)

    # Step 5: Disclaimer enforcement
    if hasattr(validated, "disclaimer"):
        object.__setattr__(validated, "disclaimer", DISCLAIMER_TEXT)
    elif hasattr(validated, "answer"):
        answer = ensure_disclaimer(validated.answer)  # type: ignore[union-attr]
        object.__setattr__(validated, "answer", answer)

    # Step 6: PII masking in text fields
    for field in ("answer", "summary", "rationale", "assessment"):
        if hasattr(validated, field):
            original = getattr(validated, field)
            masked = mask_pii(str(original))
            if masked != original:
                object.__setattr__(validated, field, masked)

    return validated
