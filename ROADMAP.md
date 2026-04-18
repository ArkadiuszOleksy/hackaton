# Kompleksowa Roadmapa Techniczna - Moduł M4 (Gateway) i DevOps

**Rola:** P4 (Support / DevOps / QA)
**Stack Gateway:** Python 3.12, FastAPI, httpx, slowapi (rate-limit)
[cite_start]**Złożoność M4:** Niska (~300 LOC), ale krytyczna biznesowo (100% ruchu z frontendu przechodzi tędy)[cite: 58, 60, 62].

---

## Faza 0: "Godzina Zero" i Start Hackathonu (Godziny 0-2)
*To zadania punktowe z ogólnego "Checklistu startowego", za które jako DevOps jesteś w dużej mierze odpowiedzialny.*

- [x] [cite_start]**0-1h:** Skonfiguruj repozytorium GitHub (monorepo), ustaw branch protection na `main`[cite: 160].
- [x] [cite_start]**0-1h:** Przygotuj wspólny plik `docker-compose.yml` z 4 placeholderami, aby każdy w zespole mógł podpiąć swój moduł[cite: 166].
- [x] [cite_start]**0-1h:** Uruchom GitHub Actions CI z zadaniami dla całego monorepo: lintowanie (`ruff`), sprawdzanie typów (`mypy`), testy (`pytest`) i buildowanie obrazów Docker[cite: 148]. [cite_start]CI musi być "zielone" na pustym kodzie[cite: 167].
- [x] **1-2h:** Weź udział w spotkaniu ustalającym kontrakty OpenAPI (tzw. Contract-first development). [cite_start]Dopilnuj, by kontrakt `contracts/gateway.yaml` został zatwierdzony przez P1 (Tech Lead) i P3 (Frontend) [cite: 111, 112, 163-165].

---

## Faza 1: Gateway Skeleton i Deploy (Godziny 2-7)

- [x] [cite_start]**2-4h:** Stwórz strukturę aplikacji FastAPI (`services/gateway-service/app`) z obsługą CORS[cite: 68, 148].
- [x] [cite_start]**2-4h:** Zaimplementuj agregację health-checków: wywołaj `/health` z M1 i M2, złącz wyniki i wystaw na `GET /health`[cite: 67, 71].
- [ ] **2-4h:** Zaimplementuj proste ścieżki Proxy (przekierowanie 1:1 za pomocą `httpx`):
    - [cite_start]`GET /api/legal-acts` -> proxy do M1 [cite: 71]
    - [cite_start]`GET /api/legal-acts/{id}` -> proxy do M1 [cite: 71]
    - [cite_start]`POST /api/qa` -> proxy do M2 [cite: 71, 72]
    - [cite_start]`POST /api/analyze/impact` -> proxy do M2 
    - [cite_start]`POST /api/analyze/trends` -> proxy do M2 
- [ ] **2-4h:** Zaimplementuj ścieżki wymagające logiki:
    - [cite_start]`POST /api/analyze/patent-check` -> **Wzorzec Fan-out:** Musisz najpierw pobrać dane z M1, a następnie połączyć je i wysłać do M2.
    - [cite_start]`POST /auth/login` -> Opcjonalna autoryzacja JWT (weryfikacja), reszta endpointów domyślnie otwarta (anonimowa).
- [ ] [cite_start]**4-7h:** Przygotuj deployment na środowisku stagingowym (Hetzner lub Fly.io)[cite: 148].
- [ ] [cite_start]**4-7h:** Podepnij darmową domenę i skonfiguruj HTTPS używając Caddy lub Traefik[cite: 148].
- [ ] [cite_start]**Milestone H+6 (Bramka):** Sprawdź i potwierdź zespołowi, że `docker-compose up` podnosi wszystkie bazy i 4 moduły (każdy na swoim porcie), a Twój zbiorczy `/health` działa[cite: 127].

---

## Faza 2: Kontrola Ruchu, QA i Bezpieczeństwo (Godziny 7-14)

- [ ] **7-9h:** Przeprowadź QA manualne. "Przeklikaj" Gatewayem wszystkie endpointy, upewniając się, że "Happy Path" działa od frontendu aż po bazy danych. [cite_start]Zgłaszaj bugi na bieżąco[cite: 148].
- [ ] **12-14h:** Zabezpiecz moduł AI przed nadużyciami. Skonfiguruj Rate-limiting (używając biblioteki `slowapi` z Redisem). [cite_start]W przypadku przekroczenia limitu zwracaj błąd `RATE_LIMITED` (429)[cite: 65, 90].
- [ ] [cite_start]**12-14h:** Wykonaj testy obciążeniowe przy użyciu `k6` — zasymuluj ruch rzędu 100 Requestów na Sekundę (RPS) na endpoint `/api/qa`[cite: 148].
- [ ] [cite_start]**12-14h:** Przeprowadź skanowanie bezpieczeństwa (Basic security scan) kontenerów za pomocą narzędzia `trivy`[cite: 148].

---

## Faza 3: Backupy, Stabilizacja i Finał (Godziny 14-24)

- [ ] **14-17h:** Nagraj płynne, 2-minutowe Demo wideo (używając np. OBS Studio). [cite_start]To krytyczny "plan B" na wypadek problemów z siecią podczas oceny projektu[cite: 148].
- [ ] **17-19h:** Dopracuj dokumentację techniczną. [cite_start]Upewnij się, że wspólny kod ma uzupełniony plik `README.md` oraz wygeneruj wersję `README.pdf` specjalnie dla Jury[cite: 148].
- [ ] [cite_start]**19-22h:** Przeprowadź ostateczne testy przepływu z użytkownikiem (End-to-End Demo flow) na publicznym URL-u ze środowiska stagingowego[cite: 148].
- [ ] **Milestone H+23 (Bramka):** Potwierdzenie gotowości infrastruktury. [cite_start]System na Stagingu musi być stabilny, a "flow" przetestowane[cite: 127].
- [ ] [cite_start]**22-24h:** Podczas właściwego Demo: pełnisz rolę "Operatora" – nadzorujesz logi, odpowiadasz za przełączanie ekranów/widoków, podczas gdy Tech Lead (P1) tłumaczy logikę[cite: 127, 148].

---

## Restrykcyjne Wymogi Techniczne (Umowa wewnątrz zespołu)

[cite_start]Twoje API to "twarda umowa" z modułami[cite: 74]. Zadbaj w kodzie M4 o następujące rzeczy:
1. **Correlation ID:** Generuj UUID v4 dla przychodzącego żądania i wstrzykuj go jako nagłówek `X-Request-ID` do requestów idących do M1 i M2. [cite_start]Dodawaj go również do opcjonalnego obiektu `"meta"` w odpowiedzi[cite: 68, 79, 82, 86].
2. [cite_start]**Kody Błędów:** W przypadku gdy M1 lub M2 "padnie" (down), Gateway nie może rzucić wyjątku 500. Musi złapać błąd `httpx` i zwrócić zunifikowany JSON (Uniform response envelope) ze strukturą `"error"` oraz statusem `UPSTREAM_ERROR` (502) lub `UPSTREAM_TIMEOUT` (504) [cite: 69, 88-90].
3. [cite_start]**Formatowanie Danych:** Pilnuj, by Gateway przepuszczał (lub formatował) daty w formacie ISO 8601 UTC oraz trzymał się konwencji `snake_case` dla pól w JSON-ach [cite: 76-78].