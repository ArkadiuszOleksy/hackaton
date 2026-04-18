# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# M2 · ai-service (CivicLens)

> Plik instrukcyjny dla asystenta Claude Code pracującego nad modułem **M2 (ai-service)**
> projektu **CivicLens** w trakcie 24-godzinnego hackathonu.
> Rola Claude: **pair programmer Tech Leada (P1)** — ma pomagać szybko i bezpiecznie
> dostarczyć moduł LLM/RAG, nie rozpraszając się na cudzą robotę (M1/M3/M4).

---

## 1. Misja modułu (one-liner)

M2 to **„mózg LLM"** CivicLensa: orkiestruje RAG na aktach prawnych z M1, wywołuje
modele przez OpenRouter, zwraca **ustrukturyzowane, ocytowane odpowiedzi** (Q&A,
Impact, Patent-Check, Trendy, Summarize) z **guardrailami** chroniącymi przed
halucynacjami.

**Granica:** M2 **nie** trzyma danych domeny (to M1), **nie** serwuje UI (to M3),
**nie** robi rate-limitingu brzegowego ani autoryzacji (to M4). Jeśli coś ciągnie
Cię w tamte obszary — zatrzymaj się i zapytaj.

---

## 2. Stack techniczny (obowiązujący)

| Warstwa             | Wybór                                                  |
| ------------------- | ------------------------------------------------------ |
| Język               | Python 3.12                                            |
| Framework HTTP      | FastAPI + Uvicorn                                      |
| Walidacja           | Pydantic v2 (strict mode)                              |
| HTTP klient         | `httpx` (async, timeout 10 s, retry 3× exp. backoff via `tenacity`) |
| LLM gateway         | OpenRouter (Claude Sonnet/Haiku → GPT-4o-mini → Mixtral) |
| Orkiestracja RAG    | `langchain` **lub** `llamaindex` — wybierz JEDNO, nie mieszaj |
| Templating promptów | Jinja2 (pliki `.j2` w `app/prompts/`)                  |
| Cache               | Redis (SHA-256(prompt) → JSON response, TTL 7 dni)     |
| Config              | `pydantic-settings` (env-first, `.env` tylko lokalnie) |
| Port                | **8002** (niezmienny)                                  |
| Repo                | `services/ai-service/`                                 |

**Zakazane w M2:** własne ORM-y (M1 to robi), bezpośrednie wywołania Anthropic/OpenAI SDK
(idziemy wyłącznie przez OpenRouter), synchronii blokujące `requests` (tylko `httpx` async).

---

## 3. Kontrakt API (single source of truth)

Kontrakt OpenAPI jest w `contracts/ai.yaml`. **Nie zmieniaj go bez PR i review od
konsumenta (M4 gateway).** Endpoints:

```
GET  /health                  → {status, db:"n/a", redis, openrouter}
POST /qa                      → RAG Q&A o ustawie
POST /analyze/impact          → „kto zyskuje / kto traci" (stakeholder analysis)
POST /analyze/patent-check    → czy pomysł podobny do istniejących patentów
POST /analyze/trends          → sentiment + tematy z pogłosek
POST /summarize               → streszczenie aktu w 3 zdaniach
```

Każda odpowiedź używa **uniform envelope**:

```json
{ "data": { ... }, "meta": { "request_id": "...", "cached": false, "took_ms": 1234 } }
```

Błędy:

```json
{ "error": { "code": "LLM_ERROR", "message": "...", "details": {}, "request_id": "..." } }
```

Dopuszczone kody błędów w M2: `BAD_REQUEST`, `NOT_FOUND` (gdy `act_id` nie istnieje
w M1), `UPSTREAM_ERROR`, `UPSTREAM_TIMEOUT`, `LLM_ERROR`, `RATE_LIMITED`, `INTERNAL_ERROR`.

---

## 4. Integracja z M1 (data-service)

- Base URL: env `DATA_SERVICE_URL` (np. `http://data-service:8001`).
- **M2 woła M1 bezpośrednio** — nie przez gateway (wydajność).
- Każde wywołanie: `timeout=10s`, `retries=3` exp. backoff (tenacity).
- **Circuit breaker:** po 5 kolejnych błędach → oznacz M1 jako DOWN, zwróć `UPSTREAM_ERROR`.
- **X-Request-ID** propaguj z wejścia (gateway → M2 → M1) — ten sam ID w logach.

Endpointy M1, z których M2 faktycznie korzysta:
- `GET /legal-acts/{id}` — metadane + pełny tekst aktu
- `GET /articles/search?q=...&top_k=8` — semantic search (pgvector) → kontekst RAG
- `GET /patents?q=...&top_k=10` — semantic search patentów (dla patent-check)
- `GET /trends/sources` — ostatnie 50 artykułów RSS (dla /analyze/trends)

Nie zakładaj innych. Jeśli potrzebujesz nowego — uzgodnij z P2 (owner M1) **zanim** napiszesz klienta.

---

## 5. Architektura wewnętrzna M2 (Clean-ish)

```
services/ai-service/
├── app/
│   ├── main.py                  # FastAPI entrypoint, routers, middleware
│   ├── config.py                # pydantic-settings
│   ├── api/                     # routery (qa, impact, patent, trends, summarize, health)
│   ├── domain/                  # czyste pydantic models + reguły (bez HTTP/LLM)
│   │   ├── models.py
│   │   └── rules.py
│   ├── rag/                     # retrieval + prompt assembly
│   │   ├── retriever.py         # klient M1 /articles/search
│   │   └── builder.py           # montaż kontekstu → prompt
│   ├── llm/
│   │   ├── openrouter.py        # klient + fallback chain
│   │   ├── models.py            # enum dostępnych modeli
│   │   └── budget.py            # kontrola kosztów/tokenów
│   ├── prompts/                 # pliki .j2 — JEDYNE miejsce na teksty promptów
│   │   ├── qa.j2
│   │   ├── impact.j2
│   │   ├── patent_check.j2
│   │   ├── trends.j2
│   │   └── summarize.j2
│   ├── guardrails/
│   │   ├── citations.py         # walidacja że cytaty istnieją w źródłach
│   │   ├── schema.py            # walidacja JSON output vs Pydantic
│   │   └── injection.py         # detekcja prompt injection (prosty regex+heurystyka)
│   ├── cache/
│   │   └── redis_cache.py       # SHA-256(prompt) → response, TTL 7 dni
│   └── clients/
│       └── data_service.py      # httpx async klient M1 + circuit breaker
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

**Zasada:** `domain/` nie importuje `httpx`, `redis`, `openai` ani niczego sieciowego.
Granica jest twarda — ułatwia to testy i podmianę dostawców.

---

## 6. Prompt engineering — zasady obowiązujące

Claude, ty jesteś prompt engineerem Anthropic — stosuj poniższe reguły **bez wyjątku**:

1. **Jeden prompt = jeden plik `.j2`** w `app/prompts/`. Nie sklejaj promptów f-stringami w kodzie biznesowym.
2. **Struktura promptu (zawsze ta sama kolejność):**
   - `<system>` — rola, zasady, język (polski), format wyjścia.
   - `<context>` — cytowane fragmenty z M1 (numerowane `[1]`, `[2]`, …) z `article_id` i `article_number`.
   - `<task>` — konkretna instrukcja dla tego endpointu.
   - `<output_schema>` — JSON schema, którego LLM MUSI przestrzegać.
   - `<user_input>` — pytanie/treść od użytkownika (sanityzowana).
3. **Język odpowiedzi: polski.** System prompt jawnie to wymusza.
4. **Temperature:** 0.1 dla QA/Impact/PatentCheck (deterministyczne), 0.3 dla Summarize, 0.5 dla Trends (szerszy wgląd).
5. **Top-K retrievalu:** domyślnie 8 fragmentów; pozwól override w requeście (max 15).
6. **JSON output zawsze** — używaj `response_format={"type":"json_object"}` gdzie OpenRouter wspiera; inaczej instrukcja w system prompcie + walidacja Pydantic po stronie M2.
7. **Disclaimer** — każda odpowiedź użytkowa ma pole `disclaimer`: „To nie jest porada prawna. Skonsultuj się z prawnikiem." Nie skracaj, nie usuwaj.
8. **Cytaty obowiązkowe** — każde twierdzenie w `answer` musi mieć `citations: [article_id]`. Guardrail odrzuca odpowiedzi bez cytatów dla `/qa` i `/analyze/impact`.
9. **Prompt injection** — przed wklejeniem `user_input` przepuść przez `guardrails/injection.py`. Podejrzane wzorce (np. „ignore previous instructions", „systemowa rola:") → `BAD_REQUEST`.
10. **Bez PII w logach** — loguj hash promptu, nie jego treść.

---

## 7. Model routing & fallback

OpenRouter wybiera model wg zadania (konfiguracja w `app/llm/models.py`):

| Endpoint              | Primary                    | Fallback 1        | Fallback 2        |
| --------------------- | -------------------------- | ----------------- | ----------------- |
| `/qa`                 | `anthropic/claude-haiku-4.5` | `openai/gpt-4o-mini` | `mistralai/mixtral-8x7b` |
| `/analyze/impact`     | `anthropic/claude-sonnet-4.6` | `openai/gpt-4o`      | `anthropic/claude-haiku-4.5` |
| `/analyze/patent-check` | `anthropic/claude-haiku-4.5` | `openai/gpt-4o-mini` | — |
| `/analyze/trends`     | `anthropic/claude-haiku-4.5` | `openai/gpt-4o-mini` | — |
| `/summarize`          | `anthropic/claude-haiku-4.5` | `openai/gpt-4o-mini` | — |

Trigger fallbacku: `5xx` od OpenRouter, `timeout>30s`, `LLM_ERROR` przy walidacji schemy
(jednokrotny retry na innym modelu). Po wyczerpaniu łańcucha → zwróć `LLM_ERROR`.

**Budżet (H+0…H+24):** miękki limit **100 USD/dzień**. Monitor w `llm/budget.py`;
po przekroczeniu 80 USD → log warn, po 100 USD → auto-throttle do fallbacku `haiku`/`mini` only.

---

## 8. Cache (Redis)

- Klucz: `ai:{endpoint}:{sha256(normalize(prompt_full))}`.
- Wartość: cała odpowiedź `data{}` (JSON).
- TTL: 7 dni (`CACHE_TTL_SECONDS=604800`).
- `meta.cached=true` gdy hit; `took_ms` liczone od wejścia do handlera (nie od LLM).
- **Nie cache'uj** gdy `temperature>0.2` ORAZ request ma flagę `no_cache: true`.
- Inwalidacja: przy zmianie wersji promptu (`prompt_version` zawarty w haszu klucza).

---

## 9. Guardrails — checklist przed zwróceniem odpowiedzi

Każda odpowiedź LLM przechodzi przez pipeline walidacyjny w tej kolejności:

1. **JSON parse** — jeśli nie parsuje → retry 1× z „Reply with VALID JSON only.".
2. **Pydantic validate** — schemat dla danego endpointu; błąd → retry 1× lub fallback model.
3. **Citation existence** — dla każdego `article_id` w `citations` zapytaj M1
   `GET /legal-acts/{act_id}` i sprawdź czy artykuł istnieje. Jeżeli nie → odrzuć
   odpowiedź (retry lub `LLM_ERROR`).
4. **Citation grounding** (best-effort) — dla `/qa` sprawdź czy fragment tekstu
   z `text_fragment` występuje w oryginalnym artykule (substring/fuzzy≥0.8).
5. **Disclaimer obecny** — wymuś dopisanie jeśli LLM go pominął.
6. **No-PII scan** — prosty regex na PESEL/NIP/email w `answer`; jeśli znaleziono → maskuj.

---

## 10. Obserwowalność

- **Logi:** JSON (structlog), pola: `ts, level, service="ai-service", request_id, endpoint, model, tokens_in, tokens_out, cost_usd, cache_hit, took_ms`.
- **Metryki Prometheus** (endpoint `/metrics`): `ai_requests_total{endpoint,status}`,
  `ai_llm_tokens_total{model,direction}`, `ai_llm_cost_usd_total{model}`,
  `ai_cache_hits_total`, `ai_latency_seconds_bucket`.
- **Tracing:** OpenTelemetry (opcjonalnie w MVP); zawsze propaguj `X-Request-ID`.
- **Health:** `/health` agreguje: samo M2 + ping Redis + ping OpenRouter (HEAD `/models`, TTL 30 s).

---

## 11. Deliverables M2 (MVP) i timeline P1

| Godz.   | Deliverable                                                           |
| ------- | --------------------------------------------------------------------- |
| 0–2 h   | Kickoff, OpenAPI `contracts/ai.yaml` zatwierdzony przez zespół        |
| 2–4 h   | FastAPI skeleton, `/health`, config, struktura katalogów              |
| 4–7 h   | OpenRouter client + fallback chain + prompt `qa.j2` + happy-path test |
| 7–11 h  | RAG pipeline: retriever (M1) → builder → LLM → odpowiedź z cytatami   |
| 11–14 h | Impact Analyzer + Patent Check (prompty + Pydantic schemas)           |
| 14–17 h | Guardrails (citations, injection), Redis cache, integracja z M4       |
| 17–19 h | Bugfixy + koordynacja końcowej integracji                             |
| 19–21 h | Demo scenariusz: 3 ustawy × po 2 pytania                              |
| 21–24 h | Pitch (P1 prowadzi)                                                   |

**Definition of Done dla M2:**
- Wszystkie 6 endpointów zwraca poprawny envelope i przechodzi Pydantic walidację.
- `docker compose up ai-service` wstaje w < 30 s i `/health` jest zielony.
- Fallback chain działa (test: celowo podaj zły klucz primary → leci na fallback).
- Cache hit widoczny w logach przy powtórzonym requeście.
- Guardrail odrzuca odpowiedź bez cytatów w teście jednostkowym.
- Pokrycie testami warstwy `domain/` ≥ 70%.

---

## 12. Zmienne środowiskowe (wymagane)

```
OPENROUTER_API_KEY=...            # secret, NIGDY do repo
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DATA_SERVICE_URL=http://data-service:8001
REDIS_URL=redis://redis:6379/0
CACHE_TTL_SECONDS=604800
LLM_TIMEOUT_SECONDS=30
LLM_DAILY_BUDGET_USD=100
LOG_LEVEL=INFO
PROMPT_VERSION=v1                 # bump przy zmianie promptów → cache invalidation
ENVIRONMENT=dev|staging|prod
```

---

## 13. Zasady pracy dla Claude (ty, asystencie)

**Kiedy pomagasz P1 przy M2:**

1. **Zawsze zaczynaj od kontraktu.** Przed kodem sprawdź `contracts/ai.yaml`. Jeśli
   kontrakt nie zgadza się z pomysłem P1 — zasugeruj zmianę kontraktu **najpierw**.
2. **Trzymaj się stacku z sekcji 2.** Nie proponuj alternatyw (Flask, requests, Pinecone, itd.) chyba że P1 o to wprost poprosi.
3. **Wszystkie teksty promptów → do `app/prompts/*.j2`.** Nie wklejaj wielolinijkowych promptów w kodzie Pythona.
4. **Odpowiedzi LLM zawsze walidowane Pydantic.** Nie zakładaj że JSON jest OK — waliduj.
5. **Minimalne PR-y (<300 LOC).** Jeden PR = jedna feature (np. „dodaj endpoint /summarize").
6. **Test przed merge.** Każdy endpoint ma minimum 1 happy-path test + 1 error test.
7. **Nie dotykaj kodu M1/M3/M4.** Jeśli widzisz problem tam — zgłoś P1, on zadecyduje kto to robi.
8. **Zero sekretów w kodzie.** Gdy widzisz hardcoded klucz — przerwij i popraw na env.
9. **Logi bez PII** — loguj hashe, nie treści zapytań.
10. **Polski w odpowiedziach dla użytkownika** (pole `answer`, `summary`, `rationale`),
    angielski w kodach błędów i nazwach pól JSON.

**Czego nie rób:**

- Nie twórz nowych endpointów „bo się przyda". Trzymaj się listy z sekcji 3.
- Nie dokładaj zależności bez zgody P1 (każda biblioteka = ryzyko).
- Nie eksponuj `/docs` publicznie w prod — tylko za VPN/auth.
- Nie używaj OpenAI/Anthropic SDK bezpośrednio — zawsze OpenRouter.
- Nie wywołuj LLM w testach jednostkowych — mockuj `openrouter.py`.

---

## 14. Quick reference — komendy

```bash
# Lokalny dev (z katalogu services/ai-service/)
uv sync
uvicorn app.main:app --reload --port 8002

# Docker (z roota repo)
docker compose -f infra/docker-compose.yml up ai-service --build

# Testy
pytest services/ai-service -q
pytest services/ai-service --cov=app --cov-report=term-missing

# Pojedynczy test
pytest services/ai-service/tests/test_guardrails.py::test_citation_missing -v

# Lint i formatowanie
uv run ruff check app/
uv run ruff format app/
uv run mypy app/ --ignore-missing-imports

# Mock M1 (gdy P2 jeszcze nie skończył)
npx @stoplight/prism-cli mock contracts/data.yaml --port 8001

# Sanity-check OpenRouter
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models | jq '.data[].id' | head
```

---

## 15. Kontakt & eskalacja

- **Właściciel M2:** P1 (Tech Lead).
- **Konsument M2:** M4 gateway (P4) — zmiana kontraktu wymaga jego review.
- **Dostawca danych:** M1 (P2) — nowy endpoint M1? uzgodnij w Discord `#hackathon-civiclens`.
- **Blokery > 30 min** → stand-up poza harmonogramem (co 4 h i tak jest regularny).

---

*Wersja: 1.0 · kwiecień 2026 · dokument żyjący — aktualizuj przy każdej zmianie kontraktu lub stacku.*
