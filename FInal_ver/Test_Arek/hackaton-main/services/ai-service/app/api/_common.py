import time
from typing import Any


def make_envelope(data: dict[str, Any], request_id: str, cached: bool, took_ms: int) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {"request_id": request_id, "cached": cached, "took_ms": took_ms},
    }


def make_error(code: str, message: str, request_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
