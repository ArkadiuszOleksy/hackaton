import time
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api._common import elapsed_ms, make_envelope, make_error
from app.clients.data_service import NotFoundError
from app.domain.models import SummarizeRequest, SummarizeResponse
from app.domain.rules import ENDPOINT_TEMPERATURES, compute_cache_key
from app.guardrails import run_guardrails
from app.llm.openrouter import LLMError
from app.rag.builder import build_messages

log = structlog.get_logger()
router = APIRouter(tags=["summarize"])


@router.post("/summarize")
async def summarize_endpoint(body: SummarizeRequest, request: Request) -> JSONResponse:
    start = time.monotonic()
    request_id: str = getattr(request.state, "request_id", "unknown")
    cache = request.app.state.redis_cache
    settings = request.app.state.settings
    data_client = request.app.state.data_client
    openrouter = request.app.state.openrouter

    cache_key = compute_cache_key("/summarize", body.act_id, settings.prompt_version)

    if not body.no_cache:
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=make_envelope(cached, request_id, cached=True, took_ms=elapsed_ms(start)))

    # Fetch the full legal act text (returns mock data when DRY_RUN=true)
    try:
        act = await data_client.get_legal_act(body.act_id, request_id=request_id)
    except NotFoundError:
        return JSONResponse(
            status_code=404,
            content=make_error("NOT_FOUND", f"Legal act '{body.act_id}' not found.", request_id),
        )
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("UPSTREAM_ERROR", str(exc), request_id))

    act_text = act.get("full_text", act.get("content", ""))
    messages = build_messages(
        "summarize.j2",
        [],
        f"Proszę streść akt o id: {body.act_id}",
        extra={"act_text": act_text},
    )

    try:
        raw, model_used, tokens_in, tokens_out = await openrouter.complete_with_fallback(
            messages,
            "/summarize",
            temperature=ENDPOINT_TEMPERATURES["/summarize"],
            response_format={"type": "json_object"},
            cache=cache,
        )
    except LLMError as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", str(exc), request_id))

    async def retry_fn(hint: str) -> str:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": hint},
        ]
        content, _, _, _ = await openrouter.complete_with_fallback(
            retry_messages, "/summarize", temperature=0.0, cache=cache
        )
        return content

    try:
        validated = await run_guardrails(
            raw, SummarizeResponse, [], data_client, request_id,
            retry_fn=retry_fn, require_citations=False,
        )
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", f"Guardrail failed: {exc}", request_id))

    data: dict[str, Any] = validated.model_dump()
    await cache.set(cache_key, data, settings.cache_ttl_seconds)

    log.info("summarize.complete", request_id=request_id, model=model_used, tokens_in=tokens_in, tokens_out=tokens_out, took_ms=elapsed_ms(start))
    return JSONResponse(content=make_envelope(data, request_id, cached=False, took_ms=elapsed_ms(start)))
