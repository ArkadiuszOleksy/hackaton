from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import uuid

app = FastAPI(title="CivicLens Gateway API (M4)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Adresy modułów (domyślnie localhost na portach wyznaczonych w Wordzie)
M1_URL = "http://localhost:8001"
M2_URL = "http://localhost:8002"


@app.get("/health")
async def aggregated_health_check():
    status_response = {"gateway": "ok", "m1_data": "unknown", "m2_ai": "unknown"}
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            r1 = await client.get(f"{M1_URL}/health")
            status_response["m1_data"] = "ok" if r1.status_code == 200 else "error"
        except httpx.RequestError:
            status_response["m1_data"] = "down"

        try:
            r2 = await client.get(f"{M2_URL}/health")
            status_response["m2_ai"] = "ok" if r2.status_code == 200 else "error"
        except httpx.RequestError:
            status_response["m2_ai"] = "down"

    return status_response


async def forward_request(method: str, url: str, request: Request, payload: dict = None):
    """Wspólna funkcja proxy obsługująca X-Request-ID i Uniform Error Response."""
    # 1. Tworzymy nowe, lub pobieramy istniejące X-Request-ID (Correlation ID)
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    headers = {"X-Request-ID": req_id}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            if method == "GET":
                response = await client.get(url, headers=headers, params=request.query_params)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=payload)

            # Jeśli moduł wewnętrzny rzuci błędem
            if response.status_code >= 500:
                return JSONResponse(
                    status_code=502,
                    content={"error": {"code": "UPSTREAM_ERROR", "message": "Moduł wewnętrzny zwrócił błąd",
                                       "request_id": req_id}}
                )

            # Poprawna odpowiedź
            return JSONResponse(status_code=response.status_code, content=response.json())

        except httpx.RequestError:
            # Łapiemy sytuację, gdy np. M1 w ogóle nie jest włączone
            return JSONResponse(
                status_code=502,
                content={
                    "error": {"code": "UPSTREAM_ERROR", "message": f"Brak komunikacji z {url}", "request_id": req_id}}
            )


# --- PROSTE PROXY DO M1 (Dane) ---
@app.get("/api/legal-acts")
async def proxy_legal_acts(request: Request):
    return await forward_request("GET", f"{M1_URL}/legal-acts", request)


@app.get("/api/legal-acts/{act_id}")
async def proxy_legal_acts_id(act_id: str, request: Request):
    return await forward_request("GET", f"{M1_URL}/legal-acts/{act_id}", request)


# --- PROSTE PROXY DO M2 (AI) ---
@app.post("/api/qa")
async def proxy_qa(request: Request):
    payload = await request.json()
    return await forward_request("POST", f"{M2_URL}/qa", request, payload)


@app.post("/api/analyze/impact")
async def proxy_impact(request: Request):
    payload = await request.json()
    return await forward_request("POST", f"{M2_URL}/analyze/impact", request, payload)


@app.post("/api/analyze/trends")
async def proxy_trends(request: Request):
    payload = await request.json()
    return await forward_request("POST", f"{M2_URL}/analyze/trends", request, payload)


# --- ZAAWANSOWANY FAN-OUT (Wymaga logiki) ---
@app.post("/api/analyze/patent-check")
async def patent_check_fan_out(request: Request):
    payload = await request.json()
    req_id = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # 1. Pobieramy z Frontendu o co pyta użytkownik (np. idea = "panele słoneczne")
            query = payload.get("idea", "")

            # 2. Pytamy moduł M1 (dane) o podobne patenty z bazy UPRP
            m1_resp = await client.get(f"{M1_URL}/patents?q={query}", headers={"X-Request-ID": req_id})
            patenty_z_m1 = m1_resp.json() if m1_resp.status_code == 200 else {}

            # 3. Dodajemy te dane do paczki od użytkownika
            payload["m1_context"] = patenty_z_m1

            # 4. Wysyłamy wzbogaconą paczkę do modelu LLM w M2, żeby to ocenił
            m2_resp = await client.post(f"{M2_URL}/analyze/patent-check", json=payload,
                                        headers={"X-Request-ID": req_id})

            if m2_resp.status_code >= 500:
                return JSONResponse(status_code=502, content={
                    "error": {"code": "UPSTREAM_ERROR", "message": "Moduł AI zawiódł", "request_id": req_id}})
            return JSONResponse(status_code=m2_resp.status_code, content=m2_resp.json())

        except httpx.RequestError:
            return JSONResponse(status_code=502, content={
                "error": {"code": "UPSTREAM_ERROR", "message": "Błąd komunikacji podczas łączenia M1 i M2",
                          "request_id": req_id}})