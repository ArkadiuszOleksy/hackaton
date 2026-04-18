import json
import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from app.llm.openrouter import LLMError, OpenRouterClient
from app.llm.models import LLMModel


def _make_client() -> tuple[OpenRouterClient, httpx.AsyncClient]:
    http = httpx.AsyncClient()
    client = OpenRouterClient(http)
    return client, http


def _mock_response(content: str, tokens_in: int = 10, tokens_out: int = 20) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out},
    }


MESSAGES = [{"role": "user", "content": "test question"}]


@pytest.mark.asyncio
@respx.mock
async def test_complete_success():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_mock_response('{"answer": "ok"}'))
    )
    client, http = _make_client()
    async with http:
        content, tin, tout = await client.complete(MESSAGES, LLMModel.CLAUDE_HAIKU, 0.1)
    assert content == '{"answer": "ok"}'
    assert tin == 10
    assert tout == 20


@pytest.mark.asyncio
@respx.mock
async def test_complete_fallback_on_500():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        # First 3 calls (primary model with retries): 500
        # Next call (fallback model): 200
        if call_count <= 1:
            return httpx.Response(500, text="server error")
        return httpx.Response(200, json=_mock_response('{"answer": "fallback ok"}'))

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=side_effect)

    client, http = _make_client()
    async with http:
        content, model_used, tin, tout = await client.complete_with_fallback(
            MESSAGES, "/qa", 0.1
        )

    assert content == '{"answer": "fallback ok"}'
    assert model_used != str(LLMModel.CLAUDE_HAIKU)


@pytest.mark.asyncio
@respx.mock
async def test_complete_all_models_fail():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="all fail")
    )
    client, http = _make_client()
    async with http:
        with pytest.raises(LLMError, match="All models failed"):
            await client.complete_with_fallback(MESSAGES, "/qa", 0.1)


@pytest.mark.asyncio
async def test_dry_run_returns_fixture(monkeypatch):
    monkeypatch.setattr("app.llm.openrouter.settings.dry_run", True)
    client = OpenRouterClient(httpx.AsyncClient())
    content, tin, tout = await client.complete(MESSAGES, LLMModel.CLAUDE_HAIKU, 0.1)
    data = json.loads(content)
    assert "answer" in data
    assert tin == 100
    assert tout == 200


@pytest.mark.asyncio
async def test_budget_throttle_uses_cheap_model(monkeypatch):
    import app.llm.budget as budget_module
    monkeypatch.setattr(budget_module, "_budget_throttled", True)
    chain = budget_module.get_model_chain("/analyze/impact")
    from app.llm.models import CHEAP_MODELS
    for model in chain:
        assert model in CHEAP_MODELS
