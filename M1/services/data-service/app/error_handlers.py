from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


STATUS_TO_CODE = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    429: "RATE_LIMITED",
    502: "UPSTREAM_ERROR",
    504: "UPSTREAM_TIMEOUT",
}


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return str(request_id)

    header_request_id = request.headers.get("X-Request-ID")
    if header_request_id:
        return header_request_id

    return str(uuid.uuid4())


def _error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: object | None = None,
) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }

    if details is not None:
        payload["error"]["details"] = details

    return payload


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    code = STATUS_TO_CODE.get(exc.status_code, "INTERNAL_ERROR")

    if isinstance(exc.detail, str):
        message = exc.detail
        details = None
    elif isinstance(exc.detail, dict):
        message = exc.detail.get("message", "Request failed.")
        details = exc.detail
    else:
        message = "Request failed."
        details = None

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=code,
            message=message,
            request_id=request_id,
            details=details,
        ),
        headers={"X-Request-ID": request_id},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = _request_id(request)

    return JSONResponse(
        status_code=400,
        content=_error_payload(
            code="BAD_REQUEST",
            message="Validation failed.",
            request_id=request_id,
            details=exc.errors(),
        ),
        headers={"X-Request-ID": request_id},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)

    return JSONResponse(
        status_code=500,
        content=_error_payload(
            code="INTERNAL_ERROR",
            message="Internal server error.",
            request_id=request_id,
        ),
        headers={"X-Request-ID": request_id},
    )