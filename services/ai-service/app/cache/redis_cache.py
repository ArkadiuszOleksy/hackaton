import json
from typing import Any

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()


class RedisCache:
    def __init__(self, redis_url: str) -> None:
        self._client: aioredis.Redis = aioredis.from_url(redis_url, decode_responses=True)  # type: ignore[assignment]

    async def get(self, key: str) -> dict[str, Any] | None:
        try:
            value = await self._client.get(key)
            return json.loads(value) if value else None
        except Exception as exc:
            log.warning("redis.get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: dict[str, Any], ttl: int) -> None:
        try:
            await self._client.setex(key, ttl, json.dumps(value))
        except Exception as exc:
            log.warning("redis.set_failed", key=key, error=str(exc))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def incr_float(self, key: str, value: float, ttl: int) -> float:
        try:
            result = await self._client.incrbyfloat(key, value)
            await self._client.expire(key, ttl)
            return float(result)
        except Exception as exc:
            log.warning("redis.incr_failed", key=key, error=str(exc))
            return 0.0

    async def get_float(self, key: str) -> float:
        try:
            val = await self._client.get(key)
            return float(val) if val else 0.0
        except Exception:
            return 0.0
