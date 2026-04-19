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
    # Mock data if DRY_RUN is enabled
    if settings.dry_run:
        return _DRY_RUN_ARTICLES[:top_k]

    # 1. Semantyczne wyszukiwanie (RAG)
    articles = await client.search_articles(q=query, top_k=top_k, request_id=request_id)
    
    # Przemapowanie pól na format oczekiwany przez prompt (id -> article_id, text -> content)
    formatted_articles = []
    for a in articles:
        formatted_articles.append({
            "article_id": str(a.get("id", a.get("article_id", ""))),
            "article_number": a.get("article_number", ""),
            "content": a.get("text", a.get("content", ""))
        })

    # 2. Jeśli mamy act_id, ale RAG nic nie znalazł (lub mało), pobieramy konkretne artykuły tej ustawy
    if act_id and len(formatted_articles) < 3:
        try:
            act_articles = await client.get_act_articles(act_id, request_id=request_id)
            for aa in act_articles:
                aid = str(aa.get("id", aa.get("article_id", "")))
                # Unikamy duplikatów
                if not any(x["article_id"] == aid for x in formatted_articles):
                    formatted_articles.append({
                        "article_id": aid,
                        "article_number": aa.get("article_number", ""),
                        "content": aa.get("text", aa.get("content", ""))
                    })
        except Exception:
            pass

    return formatted_articles[:top_k]
