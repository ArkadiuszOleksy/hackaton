import time
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

log = structlog.get_logger()

_DRY_RUN_ARTICLES = [
    {
        "article_id": "art-1",
        "article_number": "Art. 1",
        "content": "Wszyscy obywatele sa rowni wobec prawa i maja prawo do rownego traktowania przez wladze publiczne.",
    },
    {
        "article_id": "art-2",
        "article_number": "Art. 2",
        "content": "Rzeczpospolita Polska jest demokratycznym panstwem prawnym, urzeczywistniajacym zasady sprawiedliwosci spolecznej.",
    },
]

_DRY_RUN_ACT: dict[str, Any] = {
    "act_id": "dry-run",
    "title": "[DRY_RUN] Akt prawny",
    "full_text": (
        "Art. 1. Przepisy ogolne — akt reguluje prawa i obowiazki stron. "
        "Art. 2. Zakres stosowania — przepisy stosuje sie do wszystkich podmiotow. "
        "Art. 3. Definicje — uzyte pojecia maja znaczenie zgodne z ustawa."
    ),
}


class UpstreamError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class NotFoundError(UpstreamError):
    def __init__(self, resource: str = "") -> None:
        super().__init__("NOT_FOUND", f"Resource not found: {resource}")


class DataServiceClient:
    CIRCUIT_BREAKER_THRESHOLD = 5
    CIRCUIT_BREAKER_COOLDOWN = 60.0

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client
        self._base_url = settings.data_service_url.rstrip("/")
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0

    async def search_articles(self, q: str, top_k: int = 8, request_id: str = "") -> list[dict[str, Any]]:
        if settings.dry_run:
            return _DRY_RUN_ARTICLES[:top_k]
        return await self._get("/articles/search", {"q": q, "top_k": top_k}, request_id)

    async def get_act_articles(self, act_id: str, request_id: str = "") -> list[dict[str, Any]]:
        if settings.dry_run:
            return _DRY_RUN_ARTICLES
        return await self._get(f"/legal-acts/{act_id}/articles", {}, request_id)

    async def get_legal_act(self, act_id: str, request_id: str = "") -> dict[str, Any]:
        if settings.dry_run:
            return {**_DRY_RUN_ACT, "act_id": act_id}
        return await self._get(f"/legal-acts/{act_id}", {}, request_id)  # type: ignore[return-value]

    async def search_patents(self, q: str, top_k: int = 10, request_id: str = "") -> list[dict[str, Any]]:
        if settings.dry_run:
            return []
        return await self._get("/patents", {"q": q, "top_k": top_k}, request_id)

    async def get_trends_sources(self, request_id: str = "") -> list[dict[str, Any]]:
        if settings.dry_run:
            return []
        return await self._get("/trends/sources", {}, request_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TimeoutException),
        reraise=True,
    )
    async def _get(self, path: str, params: dict[str, Any], request_id: str) -> Any:
        if self._consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            if time.monotonic() < self._circuit_open_until:
                raise UpstreamError("UPSTREAM_ERROR", "M1 circuit breaker open")
            log.info("m1.circuit_breaker.half_open", path=path)

        headers: dict[str, str] = {}
        if request_id:
            headers["X-Request-ID"] = request_id

        try:
            resp = await self._http.get(
                f"{self._base_url}{path}",
                params=params,
                headers=headers,
                timeout=10,
            )
        except httpx.TimeoutException as exc:
            self._consecutive_failures += 1
            self._circuit_open_until = time.monotonic() + self.CIRCUIT_BREAKER_COOLDOWN
            log.warning("m1.timeout", path=path, failures=self._consecutive_failures)
            raise UpstreamError("UPSTREAM_TIMEOUT", f"M1 timeout on {path}") from exc

        if resp.status_code == 404:
            raise NotFoundError(path)

        if resp.status_code >= 500:
            self._consecutive_failures += 1
            self._circuit_open_until = time.monotonic() + self.CIRCUIT_BREAKER_COOLDOWN
            log.warning("m1.error", path=path, status=resp.status_code, failures=self._consecutive_failures)
            raise UpstreamError("UPSTREAM_ERROR", f"M1 {resp.status_code} on {path}")

        if resp.status_code >= 400:
            raise UpstreamError("BAD_REQUEST", f"M1 client error {resp.status_code}")

        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        
        data = resp.json()
        # Automatyczne odpakowanie envelopy "data" z M1
        if isinstance(data, dict) and "data" in data:
            return data["data"]
            
        return data
