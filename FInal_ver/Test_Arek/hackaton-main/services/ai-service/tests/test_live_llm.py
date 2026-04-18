import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from httpx import ASGITransport, AsyncClient
from fastapi.responses import JSONResponse

from app.main import app
from app.cache.redis_cache import RedisCache
from app.clients.data_service import DataServiceClient
from app.llm.openrouter import OpenRouterClient
from app.config import settings
import copy

# --- Mocks for non-LLM dependencies ---

class MockDataClient:
    def __init__(self):
        self.search_articles = AsyncMock(return_value=[
            {
                "article_id": "art-1",
                "article_number": "Art. 1",
                "content": "Wszyscy obywatele są równi wobec prawa i mają prawo do równego traktowania przez władze publiczne.",
            }
        ])
        # Make get_legal_act accept any ID and return a mock act
        # This prevents 502 errors if the LLM cites an ID not in the original search results
        self.get_legal_act = AsyncMock(side_effect=lambda act_id, request_id="": {
            "act_id": act_id,
            "full_text": f"Pełna treść aktu {act_id} dotycząca ochrony danych osobowych i równości."
        })
        self.search_patents = AsyncMock(return_value=[])
        self.get_trends_sources = AsyncMock(return_value=[])

@pytest.fixture
async def live_llm_app():
    """Setup app with real OpenRouter but mocked Data Service and Cache."""
    test_settings = copy.deepcopy(settings)
    test_settings.dry_run = False
    
    # We use a real AsyncClient for OpenRouter
    async with httpx.AsyncClient() as http_client:
        real_openrouter = OpenRouterClient(http_client)
        mock_data = MockDataClient()
        mock_cache = MagicMock(spec=RedisCache)
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache.ping = AsyncMock(return_value=True)

        app.state.openrouter = real_openrouter
        app.state.data_client = mock_data
        app.state.redis_cache = mock_cache
        app.state.settings = test_settings
        
        # Override the exception handler to print the error for debugging
        @app.exception_handler(Exception)
        async def debug_exception_handler(request, exc):
            print(f"\nDEBUG: Caught Exception in app: {type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": str(exc)})

        yield app

@pytest.fixture
async def client(live_llm_app):
    async with AsyncClient(transport=ASGITransport(app=live_llm_app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_qa_with_live_llm(client):
    """
    This test calls the actual LLM API. 
    It requires a valid OPENROUTER_API_KEY in the environment.
    """
    key = settings.openrouter_api_key
    print(f"\nDebug: Using API Key: {key[:12]}...{key[-4:]} (length: {len(key)})")
    
    if key == "sk-or-missing":
        pytest.skip("OPENROUTER_API_KEY is not set")

    resp = await client.post("/qa", json={
        "question": "Co mówi artykuł 1 o równości?",
        "no_cache": True
    })
    
    if resp.status_code != 200:
        print(f"\nError Response: {resp.json()}")
    
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "answer" in data
    assert len(data["citations"]) > 0
    print(f"\nLive LLM Answer: {data['answer']}")

@pytest.mark.asyncio
async def test_summarize_with_live_llm(client):
    """
    This test calls the actual LLM API for summarization.
    """
    if settings.openrouter_api_key == "sk-or-missing":
        pytest.skip("OPENROUTER_API_KEY is not set")

    resp = await client.post("/summarize", json={
        "act_id": "rodo",
        "no_cache": True
    })
    
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "summary" in data
    print(f"\nLive LLM Summary: {data['summary']}")
