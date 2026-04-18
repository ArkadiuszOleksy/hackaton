import pytest
import respx
import httpx

from app.llm.openrouter import LLMError, OpenRouterClient
from app.llm.models import LLMModel


MESSAGES = [{"role": "user", "content": "test"}]


def _success_response(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


@pytest.mark.asyncio
@respx.mock
async def test_fallback_on_primary_500():
    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="primary error")
        return httpx.Response(200, json=_success_response('{"ok": true}'))

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=handler)

    http = httpx.AsyncClient()
    client = OpenRouterClient(http)
    async with http:
        content, model_used, _, _ = await client.complete_with_fallback(MESSAGES, "/qa", 0.1)

    assert content == '{"ok": true}'
    assert model_used != str(LLMModel.CLAUDE_HAIKU)
    assert call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_all_models_fail_raises_llm_error():
    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="all dead")
    )

    http = httpx.AsyncClient()
    client = OpenRouterClient(http)
    async with http:
        with pytest.raises(LLMError, match="All models failed"):
            await client.complete_with_fallback(MESSAGES, "/qa", 0.1)


@pytest.mark.asyncio
@respx.mock
async def test_fallback_impact_chain():
    """Impact chain: sonnet → gpt-4o → haiku. Primary fails, falls to gpt-4o."""
    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, text="sonnet error")
        return httpx.Response(200, json=_success_response('{"result": "fallback"}'))

    respx.post("https://openrouter.ai/api/v1/chat/completions").mock(side_effect=handler)

    http = httpx.AsyncClient()
    client = OpenRouterClient(http)
    async with http:
        content, model_used, _, _ = await client.complete_with_fallback(MESSAGES, "/analyze/impact", 0.1)

    assert content == '{"result": "fallback"}'
    assert model_used == str(LLMModel.GPT4O)
