import httpx
from fastapi import APIRouter, Request

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:  # type: ignore[type-arg]
    redis_status = "error"
    openrouter_status = "error"

    cache: object | None = getattr(request.app.state, "redis_cache", None)
    if cache is not None:
        try:
            ok = await cache.ping()  # type: ignore[union-attr]
            redis_status = "ok" if ok else "error"
        except Exception:
            redis_status = "error"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.head(
                f"{settings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            openrouter_status = "ok" if resp.status_code < 500 else "error"
    except Exception:
        openrouter_status = "error"

    return {
        "status": "ok",
        "db": "n/a",
        "redis": redis_status,
        "openrouter": openrouter_status,
    }
