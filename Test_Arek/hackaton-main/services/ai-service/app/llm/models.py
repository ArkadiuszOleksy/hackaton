from enum import StrEnum


class LLMModel(StrEnum):
    CLAUDE_HAIKU = "anthropic/claude-haiku-4.5"
    CLAUDE_SONNET = "anthropic/claude-sonnet-4-6"
    GPT4O_MINI = "openai/gpt-4o-mini"
    GPT4O = "openai/gpt-4o"
    MIXTRAL = "mistralai/mixtral-8x7b"


MODEL_CHAINS: dict[str, list[LLMModel]] = {
    "/qa": [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI, LLMModel.MIXTRAL],
    "/analyze/impact": [LLMModel.CLAUDE_SONNET, LLMModel.GPT4O, LLMModel.CLAUDE_HAIKU],
    "/analyze/patent-check": [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI],
    "/analyze/trends": [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI],
    "/summarize": [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI],
}

CHEAP_MODELS: list[LLMModel] = [LLMModel.CLAUDE_HAIKU, LLMModel.GPT4O_MINI]

COST_PER_1K_TOKENS: dict[str, tuple[float, float]] = {
    LLMModel.CLAUDE_HAIKU: (0.00025, 0.00125),
    LLMModel.CLAUDE_SONNET: (0.003, 0.015),
    LLMModel.GPT4O_MINI: (0.00015, 0.0006),
    LLMModel.GPT4O: (0.005, 0.015),
    LLMModel.MIXTRAL: (0.0006, 0.0006),
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = COST_PER_1K_TOKENS.get(model, (0.001, 0.002))
    return (tokens_in / 1000) * rates[0] + (tokens_out / 1000) * rates[1]
