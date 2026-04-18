import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import uuid

M1_URL = os.getenv("M1_URL", "http://localhost:8001")
M2_URL = os.getenv("M2_URL", "http://localhost:8002")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="CivicLens Gateway API (M4)", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def aggregated_health_check(request: Request):
    status_response = {"gateway": "ok", "m1_data": "unknown", "m2_ai": "unknown"}
    client = request.app.state.http_client
    results = await asyncio.gather(
        client.get(f"{M1_URL}/health", timeout=2.0),
        client.get(f"{M2_URL}/health", timeout=2.0),
        return_exceptions=True,
    )
    r1, r2 = results
    status_response["m1_data"] = "ok" if not isinstance(r1, Exception) and r1.status_code == 200 else "down"
    status_response["m2_ai"] = "ok" if not isinstance(r2, Exception) and r2.status_code == 200 else "down"
    return status_response


async def forward_request(method: str, url: str, request: Request, payload: dict = None):
    """Wspólna funkcja proxy obsługująca X-Request-ID i Uniform Error Response."""
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    headers = {"X-Request-ID": req_id}
    client = request.app.state.http_client

    try:
        if method == "GET":
            response = await client.get(url, headers=headers, params=request.query_params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 500:
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "UPSTREAM_ERROR", "message": "Moduł wewnętrzny zwrócił błąd",
                                   "request_id": req_id}}
            )

        return JSONResponse(status_code=response.status_code, content=response.json())

    except httpx.RequestError:
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
    client = request.app.state.http_client

    try:
        query = payload.get("idea", "")

        m1_resp = await client.get(f"{M1_URL}/patents?q={query}", headers={"X-Request-ID": req_id})
        patenty_z_m1 = m1_resp.json() if m1_resp.status_code == 200 else {}

        payload["m1_context"] = patenty_z_m1

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
