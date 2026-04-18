from typing import Any
from app.clients.data_service import DataServiceClient
from app.config import settings

_DRY_RUN_ARTICLES = [
    {
        "article_id": "art-1",
        "article_number": "Art. 1",
        "content": "Wszyscy obywatele są równi wobec prawa i mają prawo do równego traktowania przez władze publiczne.",
    },
    {
        "article_id": "art-2",
        "article_number": "Art. 2",
        "content": "Rzeczpospolita Polska jest demokratycznym państwem prawnym, urzeczywistniającym zasady sprawiedliwości społecznej.",
    },
]

async def retrieve_articles(
    client: DataServiceClient,
    query: str,
    top_k: int = 8,
    act_id: str | None = None,
    request_id: str = "",
) -> list[dict[str, Any]]:
    # Mock data if DRY_RUN is enabled to allow testing AI service without M1
    if settings.dry_run:
        return _DRY_RUN_ARTICLES[:top_k]

    articles = await client.search_articles(q=query, top_k=top_k, request_id=request_id)

    if act_id:
        try:
            act = await client.get_legal_act(act_id, request_id=request_id)
            act_article = {
                "article_id": act_id,
                "article_number": "Pełny akt",
                "content": act.get("full_text", act.get("content", "")),
            }
            articles = [act_article] + articles
        except Exception:
            pass

    return articles
