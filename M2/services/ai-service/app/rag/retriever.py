from typing import Any

from app.clients.data_service import DataServiceClient


async def retrieve_articles(
    client: DataServiceClient,
    query: str,
    top_k: int = 8,
    act_id: str | None = None,
    request_id: str = "",
) -> list[dict[str, Any]]:
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
