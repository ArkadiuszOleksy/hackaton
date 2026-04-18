import time
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api._common import elapsed_ms, make_envelope, make_error
from app.domain.models import ImpactRequest, ImpactResponse, PatentCheckRequest, PatentCheckResponse, TrendsRequest, TrendsResponse
from app.domain.rules import ENDPOINT_TEMPERATURES, compute_cache_key
from app.guardrails import run_guardrails
from app.guardrails.injection import InjectionDetectedError, check_injection
from app.llm.openrouter import LLMError
from app.rag.builder import build_messages
from app.rag.retriever import retrieve_articles

log = structlog.get_logger()
router = APIRouter(prefix="/analyze", tags=["analyze"])


async def _llm_call_with_guardrails(
    request: Request,
    endpoint: str,
    messages: list[dict[str, str]],
    schema: type,
    articles: list[dict[str, Any]],
    temperature: float,
    require_citations: bool,
    request_id: str,
) -> tuple[dict[str, Any], str, int, int]:
    openrouter = request.app.state.openrouter
    data_client = request.app.state.data_client
    cache = request.app.state.redis_cache

    raw, model_used, tokens_in, tokens_out = await openrouter.complete_with_fallback(
        messages,
        endpoint,
        temperature=temperature,
        response_format={"type": "json_object"},
        cache=cache,
    )

    async def retry_fn(hint: str) -> str:
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": hint},
        ]
        content, _, _, _ = await openrouter.complete_with_fallback(
            retry_messages, endpoint, temperature=0.0, cache=cache
        )
        return content

    validated = await run_guardrails(
        raw, schema, articles, data_client, request_id,
        retry_fn=retry_fn, require_citations=require_citations,
    )
    return validated.model_dump(), model_used, tokens_in, tokens_out


@router.post("/impact")
async def impact_endpoint(body: ImpactRequest, request: Request) -> JSONResponse:
    start = time.monotonic()
    request_id: str = getattr(request.state, "request_id", "unknown")
    cache = request.app.state.redis_cache
    settings = request.app.state.settings

    try:
        check_injection(body.description)
    except InjectionDetectedError as exc:
        return JSONResponse(status_code=400, content=make_error("BAD_REQUEST", str(exc), request_id))

    cache_key = compute_cache_key("/analyze/impact", f"{body.description}|{body.act_id}", settings.prompt_version)

    if not body.no_cache:
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=make_envelope(cached, request_id, cached=True, took_ms=elapsed_ms(start)))

    try:
        articles = await retrieve_articles(
            request.app.state.data_client, body.description, body.top_k, body.act_id, request_id
        )
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("UPSTREAM_ERROR", str(exc), request_id))

    messages = build_messages("impact.j2", articles, body.description)

    try:
        data, model_used, tokens_in, tokens_out = await _llm_call_with_guardrails(
            request, "/analyze/impact", messages, ImpactResponse, articles,
            temperature=ENDPOINT_TEMPERATURES["/analyze/impact"],
            require_citations=True, request_id=request_id,
        )
    except LLMError as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", str(exc), request_id))
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", f"Guardrail failed: {exc}", request_id))

    await cache.set(cache_key, data, settings.cache_ttl_seconds)
    log.info("impact.complete", request_id=request_id, model=model_used, tokens_in=tokens_in, tokens_out=tokens_out, took_ms=elapsed_ms(start))
    return JSONResponse(content=make_envelope(data, request_id, cached=False, took_ms=elapsed_ms(start)))


@router.post("/patent-check")
async def patent_check_endpoint(body: PatentCheckRequest, request: Request) -> JSONResponse:
    start = time.monotonic()
    request_id: str = getattr(request.state, "request_id", "unknown")
    cache = request.app.state.redis_cache
    settings = request.app.state.settings
    data_client = request.app.state.data_client

    try:
        check_injection(body.idea_description)
    except InjectionDetectedError as exc:
        return JSONResponse(status_code=400, content=make_error("BAD_REQUEST", str(exc), request_id))

    cache_key = compute_cache_key("/analyze/patent-check", body.idea_description, settings.prompt_version)
    cached = await cache.get(cache_key)
    if cached:
        return JSONResponse(content=make_envelope(cached, request_id, cached=True, took_ms=elapsed_ms(start)))

    try:
        patents = await data_client.search_patents(body.idea_description, top_k=body.top_k, request_id=request_id)
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("UPSTREAM_ERROR", str(exc), request_id))

    messages = build_messages("patent_check.j2", patents, body.idea_description)

    try:
        data, model_used, tokens_in, tokens_out = await _llm_call_with_guardrails(
            request, "/analyze/patent-check", messages, PatentCheckResponse, patents,
            temperature=ENDPOINT_TEMPERATURES["/analyze/patent-check"],
            require_citations=False, request_id=request_id,
        )
    except LLMError as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", str(exc), request_id))
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", f"Guardrail failed: {exc}", request_id))

    await cache.set(cache_key, data, settings.cache_ttl_seconds)
    log.info("patent_check.complete", request_id=request_id, model=model_used, took_ms=elapsed_ms(start))
    return JSONResponse(content=make_envelope(data, request_id, cached=False, took_ms=elapsed_ms(start)))


@router.post("/trends")
async def trends_endpoint(body: TrendsRequest, request: Request) -> JSONResponse:
    start = time.monotonic()
    request_id: str = getattr(request.state, "request_id", "unknown")
    cache = request.app.state.redis_cache
    settings = request.app.state.settings
    data_client = request.app.state.data_client

    cache_key = compute_cache_key("/analyze/trends", body.topic or "", settings.prompt_version)

    # trends uses temperature=0.5 > 0.2, only cache if no_cache is False
    if not body.no_cache:
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=make_envelope(cached, request_id, cached=True, took_ms=elapsed_ms(start)))

    try:
        sources = await data_client.get_trends_sources(request_id=request_id)
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("UPSTREAM_ERROR", str(exc), request_id))

    messages = build_messages("trends.j2", sources[:50], body.topic or "")

    try:
        data, model_used, tokens_in, tokens_out = await _llm_call_with_guardrails(
            request, "/analyze/trends", messages, TrendsResponse, sources,
            temperature=ENDPOINT_TEMPERATURES["/analyze/trends"],
            require_citations=False, request_id=request_id,
        )
    except LLMError as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", str(exc), request_id))
    except Exception as exc:
        return JSONResponse(status_code=502, content=make_error("LLM_ERROR", f"Guardrail failed: {exc}", request_id))

    if not body.no_cache:
        await cache.set(cache_key, data, settings.cache_ttl_seconds)

    log.info("trends.complete", request_id=request_id, model=model_used, took_ms=elapsed_ms(start))
    return JSONResponse(content=make_envelope(data, request_id, cached=False, took_ms=elapsed_ms(start)))
