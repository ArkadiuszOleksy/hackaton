from datetime import date
from typing import TYPE_CHECKING

import structlog

from app.llm.models import CHEAP_MODELS, MODEL_CHAINS, LLMModel, estimate_cost_usd

if TYPE_CHECKING:
    from app.cache.redis_cache import RedisCache

log = structlog.get_logger()

_budget_throttled: bool = False
_BUDGET_KEY_PREFIX = "ai:budget:"
_BUDGET_TTL = 86400  # 24h


def _today_key() -> str:
    return f"{_BUDGET_KEY_PREFIX}{date.today().isoformat()}"


async def record_cost(
    cache: "RedisCache",
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> float:
    cost = estimate_cost_usd(model, tokens_in, tokens_out)
    total = await cache.incr_float(_today_key(), cost, _BUDGET_TTL)
    log.info("budget.recorded", model=model, cost_usd=cost, daily_total_usd=total)
    return total


async def check_budget_throttle(cache: "RedisCache", daily_limit: float = 100.0) -> bool:
    global _budget_throttled
    total = await cache.get_float(_today_key())
    if total >= daily_limit:
        if not _budget_throttled:
            log.warning("budget.throttled", daily_total_usd=total, limit=daily_limit)
        _budget_throttled = True
        return True
    if total >= daily_limit * 0.8:
        log.warning("budget.warn_80pct", daily_total_usd=total, limit=daily_limit)
    _budget_throttled = False
    return False


def get_model_chain(endpoint: str) -> list[LLMModel]:
    chain = MODEL_CHAINS.get(endpoint, [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI])
    if _budget_throttled:
        return [m for m in chain if m in CHEAP_MODELS] or [LLMModel.GPT4O_MINI]
    return chain
