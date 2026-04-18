from prometheus_client import Counter

llm_tokens_total = Counter(
    "ai_llm_tokens_total",
    "Total LLM tokens processed",
    ["model", "direction"],
)

llm_cost_usd_total = Counter(
    "ai_llm_cost_usd_total",
    "Total LLM cost in USD",
    ["model"],
)

cache_hits_total = Counter(
    "ai_cache_hits_total",
    "Total cache hits",
    ["endpoint"],
)
