import os
import uuid
import time
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Any, Dict
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from typing import Optional, List

class QARequest(BaseModel):
    act_id: str
    question: str
    top_k: Optional[int] = 5

class ImpactRequest(BaseModel):
    act_id: str

class PatentRequest(BaseModel):
    q: str

# Konfiguracja Rate-limitingu
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="CivicLens Gateway - Pełny Kontrakt")
app.state.limiter = limiter

# Porty lokalne
M1_URL = os.getenv("M1_URL", "http://data-service:8001")
M2_URL = os.getenv("M2_URL", "http://ai-service:8002")

# 1. Odpowiedzialność: CORS dla Frontendu (M3)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def check_health(url: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/health", timeout=1.0)
            return "ok" if resp.status_code == 200 else "down"
    except Exception:
        return "down"
# --- 4.2 Uniform Response Envelopes ---

def wrap_success(data: Any, request_id: str, took_ms: int = 0) -> Dict:
    return {
        "data": data,
        "meta": {"request_id": request_id, "cached": False, "took_ms": took_ms}
    }


def wrap_error(code: str, message: str, request_id: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id}}
    )


# --- 4.1 Middleware: X-Request-ID & Logging ---

@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.time()

    try:
        response = await call_next(request)
        took_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        return wrap_error("INTERNAL_ERROR", str(e), request_id, 500)


# --- 4.3 Kluczowe Endpointy ---

# 1. GET /health (Agregacja statusów)
@app.get("/health")
async def health_check(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            m1 = await client.get(f"{M1_URL}/health", timeout=1.0)
            m1_s = m1.json().get("status", "ok")
        except:
            m1_s = "down"
        try:
            m2 = await client.get(f"{M2_URL}/health", timeout=1.0)
            m2_s = m2.json().get("status", "ok")
        except:
            m2_s = "down"
    return wrap_success({"gateway": "ok", "m1_data": m1_s, "m2_ai": m2_s}, request.state.request_id)


# 2. GET /api/legal-acts (Proxy do M1)
@app.get("/api/legal-acts")
async def list_legal_acts(request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{M1_URL}/legal-acts", params=request.query_params)
            return wrap_success(resp.json(), request.state.request_id)
        except:
            return wrap_error("UPSTREAM_ERROR", "M1 down", request.state.request_id, 502)


# 3. GET /api/legal-acts/{id} (Proxy do M1)
@app.get("/api/legal-acts/{id}")
async def get_legal_act(id: str, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{M1_URL}/legal-acts/{id}")
            return wrap_success(resp.json(), request.state.request_id)
        except:
            return wrap_error("NOT_FOUND", "Akt nie istnieje", request.state.request_id, 404)


# 4. POST /api/qa (Proxy do M2)
@app.post("/api/qa")
async def post_qa(payload: QARequest, request: Request): # Dodaliśmy 'payload: QARequest'
    async with httpx.AsyncClient() as client:
        try:
            # Przesyłamy payload jako słownik .model_dump()
            resp = await client.post(f"{M2_URL}/qa", json=payload.model_dump(), timeout=30.0)
            return wrap_success(resp.json(), request.state.request_id)
        except Exception:
            return wrap_error("UPSTREAM_ERROR", "AI Service (M2) nie odpowiada", request.state.request_id, 502)

@app.post("/api/analyze/impact")
async def analyze_impact(payload: ImpactRequest, request: Request): # Dodaliśmy 'payload: ImpactRequest'
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/analyze/impact", json=payload.model_dump(), timeout=60.0)
            return wrap_success(resp.json(), request.state.request_id)
        except Exception:
            return wrap_error("UPSTREAM_ERROR", "Błąd podczas analizy AI", request.state.request_id, 502)

@app.post("/api/analyze/patent-check")
async def patent_check(payload: PatentRequest, request: Request): # Dodaliśmy 'payload: PatentRequest'
    async with httpx.AsyncClient() as client:
        try:
            # 1. Pobierz z M1
            m1_resp = await client.get(f"{M1_URL}/patents", params={"q": payload.q})
            # 2. Wyślij do M2
            m2_resp = await client.post(f"{M2_URL}/analyze/patent-check", json={
                "context": m1_resp.json(),
                "query": payload.q
            })
            return wrap_success(m2_resp.json(), request.state.request_id)
        except Exception:
            return wrap_error("UPSTREAM_ERROR", "Błąd integracji M1/M2", request.state.request_id, 502)
# 7. POST /api/analyze/trends (Proxy do M2)
@app.post("/api/analyze/trends")
async def analyze_trends(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/analyze/trends", json=payload)
            return wrap_success(resp.json(), request.state.request_id)
        except:
            return wrap_error("UPSTREAM_ERROR", "Błąd analizy trendów", request.state.request_id, 502)


# 8. POST /auth/login (Auth MVP)
@app.post("/auth/login")
async def login(request: Request):
    # W MVP tylko stub
    return wrap_success({"token": "jwt-token-stub", "user": "anon"}, request.state.request_id)