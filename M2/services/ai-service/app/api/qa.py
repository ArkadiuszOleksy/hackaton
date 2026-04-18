import time
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api._common import elapsed_ms, make_envelope, make_error
from app.domain.models import QARequest, QAResponse
from app.domain.rules import ENDPOINT_TEMPERATURES, compute_cache_key
from app.guardrails import run_guardrails
from app.guardrails.injection import InjectionDetectedError, check_injection
from app.llm.openrouter import LLMError
from app.rag.builder import build_messages
from app.rag.retriever import retrieve_articles

log = structlog.get_logger()
router = APIRouter(tags=["qa"])


@router.post("/qa")
async def qa_endpoint(body: QARequest, request: Request) -> JSONResponse:
    start = time.monotonic()
    request_id: str = getattr(request.state, "request_id", "unknown")
    openrouter = request.app.state.openrouter
    data_client = request.app.state.data_client
    cache = request.app.state.redis_cache
    settings = request.app.state.settings

    # 1. Injection check
    try:
        check_injection(body.question)
    except InjectionDetectedError as exc:
        return JSONResponse(
            status_code=400,
            content=make_error("BAD_REQUEST", str(exc), request_id),
        )

    # 2. Build a cache key from the full prompt concept
    cache_key = compute_cache_key(
        "/qa",
        f"{body.question}|{body.act_id}|{body.top_k}",
        settings.prompt_version,
    )

    # 3. Cache check
    if not body.no_cache:
        cached = await cache.get(cache_key)
        if cached:
            log.info("qa.cache_hit", request_id=request_id, cache_hit=True)
            return JSONResponse(
                content=make_envelope(cached, request_id, cached=True, took_ms=elapsed_ms(start))
            )

    # 4. Retrieve articles from M1
    try:
        articles = await retrieve_articles(
            data_client, body.question, body.top_k, body.act_id, request_id
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content=make_error("UPSTREAM_ERROR", str(exc), request_id),
        )

    # 5. Build prompt
    messages = build_messages("qa.j2", articles, body.question)

    # 6. LLM call with fallback
    temperature = ENDPOINT_TEMPERATURES["/qa"]
    try:
        raw, model_used, tokens_in, tokens_out = await openrouter.complete_with_fallback(
            messages,
            "/qa",
            temperature=temperature,
            response_format={"type": "json_object"},
            cache=cache,
        )
    except LLMError as exc:
        return JSONResponse(
            status_code=502,
            content=make_error("LLM_ERROR", str(exc), request_id),
        )

    # 7. Build retry function for guardrails
    async def retry_fn(hint: str) -> str:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": hint},
        ]
        content, _, _, _ = await openrouter.complete_with_fallback(
            retry_messages, "/qa", temperature=0.0, cache=cache
        )
        return content

    # 8. Guardrails
    try:
        validated = await run_guardrails(
            raw, QAResponse, articles, data_client, request_id,
            retry_fn=retry_fn, require_citations=True,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content=make_error("LLM_ERROR", f"Guardrail failed: {exc}", request_id),
        )

    data: dict[str, Any] = validated.model_dump()

    # 9. Cache store
    await cache.set(cache_key, data, settings.cache_ttl_seconds)

    log.info(
        "qa.complete",
        request_id=request_id,
        model=model_used,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cache_hit=False,
        took_ms=elapsed_ms(start),
    )
    return JSONResponse(
        content=make_envelope(data, request_id, cached=False, took_ms=elapsed_ms(start))
    )
