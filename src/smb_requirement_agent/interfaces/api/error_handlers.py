"""Translate the application-owned public error catalogue to HTTP responses."""

from __future__ import annotations

import logging
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from smb_kernel.http.body_limit import RequestBodyTooLargeError

from smb_requirement_agent.application.errors import (
    DocumentExtractionBusyError,
    DocumentExtractionTimeoutError,
    ProviderRateLimitExceededError,
)
from smb_requirement_agent.application.public_errors import (
    ERROR_CATALOGUE,
    FailureCategory,
    describe_public_error,
)

logger = logging.getLogger("smb_requirement_agent.api.errors")


HTTP_STATUS_BY_CATEGORY = {
    FailureCategory.AUTHENTICATION: 401,
    FailureCategory.AUTHORIZATION: 403,
    FailureCategory.NOT_FOUND: 404,
    FailureCategory.CONFLICT: 409,
    FailureCategory.INVALID_INPUT: 422,
    FailureCategory.PROVIDER: 502,
    FailureCategory.UNAVAILABLE: 503,
    FailureCategory.RATE_LIMITED: 429,
    FailureCategory.INTERNAL: 500,
}
ERROR_STATUS_CODES = tuple(
    (error_type, HTTP_STATUS_BY_CATEGORY[category])
    for error_type, _code, category in ERROR_CATALOGUE
)


def status_code_for(exc: Exception) -> int | None:
    return next(
        (status for error_type, status in ERROR_STATUS_CODES if isinstance(exc, error_type)), None
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register one handler for every stable public application failure."""

    async def handle(request: Request, exc: Exception) -> JSONResponse:
        public = describe_public_error(exc)
        status_code = status_code_for(exc) or 500
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        if status_code >= 500:
            logger.error(
                "%s %s failed with %s: %s [correlation_id=%s]",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
                correlation_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
        container = getattr(request.app.state, "container", None)
        debug_trace = getattr(container, "debug_trace", None)
        if debug_trace is not None:
            debug_trace.record(
                "http.mapped_error",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                error_type=type(exc).__name__,
                error=str(exc),
                exception_chain="".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ),
                correlation_id=correlation_id,
            )
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        if isinstance(exc, (DocumentExtractionBusyError, DocumentExtractionTimeoutError)):
            headers = {"Retry-After": "30"}
        if isinstance(exc, ProviderRateLimitExceededError):
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        return JSONResponse(
            status_code=status_code,
            content={
                "code": public.code,
                "message": public.message,
                "correlation_id": correlation_id,
            },
            headers=headers,
        )

    for error_type, _ in ERROR_STATUS_CODES:
        app.add_exception_handler(error_type, handle)

    async def validation_error(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        if not isinstance(exc, RequestValidationError):  # registered for that type only
            return await unhandled(request, exc)
        fields = [
            ".".join(str(part) for part in item["loc"] if part not in {"body", "query"})
            for item in exc.errors()
        ]
        message = "Request validation failed"
        if any(fields):
            message += ": " + ", ".join(field for field in fields if field)
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": message + ".",
                "correlation_id": correlation_id,
            },
        )

    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        logger.error(
            "%s %s failed unexpectedly [correlation_id=%s]",
            request.method,
            request.url.path,
            correlation_id,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "The service could not complete the request.",
                "correlation_id": correlation_id,
            },
        )

    async def body_too_large(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RequestBodyTooLargeError):  # registered for that type only
            return await unhandled(request, exc)
        return JSONResponse(
            status_code=413,
            content={
                "code": "request_body_too_large",
                "message": exc.detail,
                "correlation_id": getattr(request.state, "correlation_id", str(uuid.uuid4())),
            },
        )

    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(RequestBodyTooLargeError, body_too_large)
    app.add_exception_handler(Exception, unhandled)


__all__ = ["ERROR_STATUS_CODES", "register_error_handlers", "status_code_for"]
