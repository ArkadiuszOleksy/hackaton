import os
import uuid
import time
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Any, Dict, Optional, List
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel

class QARequest(BaseModel):
    act_id: Optional[str] = None
    question: str
    top_k: Optional[int] = 8

class ImpactRequest(BaseModel):
    act_id: Optional[str] = None
    description: str
    top_k: Optional[int] = 8

class PatentRequest(BaseModel):
    idea_description: str
    top_k: Optional[int] = 10

class SummarizeRequest(BaseModel):
    act_id: str
    no_cache: Optional[bool] = False

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
            m1 = await client.get(f"{M1_URL}/health", timeout=2.0)
            m1_s = m1.json().get("status", "ok")
        except:
            m1_s = "down"
        try:
            m2 = await client.get(f"{M2_URL}/health", timeout=2.0)
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
            data = resp.json()
            # Jeśli upstream już owrapował w "data", wyciągamy środek
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except:
            return wrap_error("UPSTREAM_ERROR", "M1 down", request.state.request_id, 502)


# 3. GET /api/legal-acts/{id} (Proxy do M1)
@app.get("/api/legal-acts/{id}")
async def get_legal_act(id: str, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{M1_URL}/legal-acts/{id}")
            if resp.status_code == 404:
                 return wrap_error("NOT_FOUND", "Akt nie istnieje", request.state.request_id, 404)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except:
            return wrap_error("UPSTREAM_ERROR", "Błąd połączenia z M1", request.state.request_id, 502)


# 4. POST /api/qa (Proxy do M2)
@app.post("/api/qa")
async def post_qa(payload: QARequest, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/qa", json=payload.model_dump(), timeout=60.0)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except Exception as e:
            return wrap_error("UPSTREAM_ERROR", f"AI Service error: {str(e)}", request.state.request_id, 502)

@app.post("/api/analyze/impact")
async def analyze_impact(payload: ImpactRequest, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/analyze/impact", json=payload.model_dump(), timeout=60.0)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except Exception as e:
            return wrap_error("UPSTREAM_ERROR", f"AI Service error: {str(e)}", request.state.request_id, 502)

@app.post("/api/analyze/patent-check")
async def patent_check(payload: PatentRequest, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/analyze/patent-check", json=payload.model_dump(), timeout=60.0)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except Exception as e:
            return wrap_error("UPSTREAM_ERROR", f"AI Service error: {str(e)}", request.state.request_id, 502)

# 7. POST /api/analyze/trends (Proxy do M2)
@app.post("/api/analyze/trends")
async def analyze_trends(request: Request):
    try:
        payload = await request.json()
    except:
        payload = {}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/analyze/trends", json=payload, timeout=60.0)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except Exception as e:
            return wrap_error("UPSTREAM_ERROR", f"Błąd analizy trendów: {str(e)}", request.state.request_id, 502)

@app.post("/api/summarize")
async def post_summarize(payload: SummarizeRequest, request: Request):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{M2_URL}/summarize", json=payload.model_dump(), timeout=60.0)
            data = resp.json()
            payload = data.get("data") if isinstance(data, dict) and "data" in data else data
            return wrap_success(payload, request.state.request_id)
        except Exception as e:
            return wrap_error("UPSTREAM_ERROR", f"AI Service error: {str(e)}", request.state.request_id, 502)


# 8. POST /auth/login (Auth MVP)
@app.post("/auth/login")
async def login(request: Request):
    return wrap_success({"token": "jwt-token-stub", "user": "anon"}, request.state.request_id)
