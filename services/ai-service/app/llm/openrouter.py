import json
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.llm.budget import get_model_chain, record_cost
from app.llm.models import LLMModel

log = structlog.get_logger()

_DRY_RUN_FIXTURE = json.dumps({
    "answer": "To jest odpowiedź testowa w trybie DRY_RUN.",
    "citations": [{"article_id": "art-1", "article_number": "Art. 1", "text_fragment": "Fragment testowy."}],
    "disclaimer": "To nie jest porada prawna. Skonsultuj się z prawnikiem.",
    "stakeholders_gaining": ["Obywatele"],
    "stakeholders_losing": ["Korporacje"],
    "rationale": "Testowe uzasadnienie.",
    "similarity_score": 0.1,
    "similar_patents": [],
    "assessment": "Niskie podobieństwo.",
    "sentiment": "neutral",
    "topics": ["prawo", "polityka"],
    "summary": "To jest testowe streszczenie aktu prawnego w trybie DRY_RUN.",
})


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class BudgetExceededError(LLMError):
    pass


class OpenRouterClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client
        self._base_url = settings.openrouter_base_url
        self._api_key = settings.openrouter_api_key
        self._timeout = settings.llm_timeout_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=True,
    )
    async def _call_api(
        self,
        messages: list[dict[str, str]],
        model: LLMModel,
        temperature: float,
        response_format: dict[str, Any] | None,
    ) -> tuple[str, int, int]:
        payload: dict[str, Any] = {
            "model": str(model),
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            resp = await self._http.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "HTTP-Referer": "https://civiclens.hackathon",
                    "X-Title": "CivicLens ai-service",
                },
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Timeout calling {model}") from exc

        if resp.status_code >= 500:
            raise LLMError(f"OpenRouter {resp.status_code} for model {model}: {resp.text[:200]}")
        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter client error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        return content, tokens_in, tokens_out

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: LLMModel,
        temperature: float,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[str, int, int]:
        if settings.dry_run:
            log.info("llm.dry_run", model=model)
            return _DRY_RUN_FIXTURE, 100, 200

        return await self._call_api(messages, model, temperature, response_format)

    async def complete_with_fallback(
        self,
        messages: list[dict[str, str]],
        endpoint: str,
        temperature: float,
        response_format: dict[str, Any] | None = None,
        cache: Any = None,
    ) -> tuple[str, str, int, int]:
        chain = get_model_chain(endpoint)
        last_exc: Exception = LLMError("No models in chain")

        for model in chain:
            try:
                content, tokens_in, tokens_out = await self.complete(
                    messages, model, temperature, response_format
                )
                if cache is not None:
                    await record_cost(cache, str(model), tokens_in, tokens_out)
                log.info("llm.success", model=model, endpoint=endpoint, tokens_in=tokens_in, tokens_out=tokens_out)
                return content, str(model), tokens_in, tokens_out
            except (LLMError, LLMTimeoutError) as exc:
                log.warning("llm.fallback", model=model, endpoint=endpoint, error=str(exc))
                last_exc = exc
                continue

        raise LLMError(f"All models failed for {endpoint}: {last_exc}") from last_exc
