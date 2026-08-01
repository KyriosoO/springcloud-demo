from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agent_runtime.api.limits import RequestBodyTooLarge, RuntimeCapacityExceeded


class RuntimeProtocolViolation(Exception):
    pass


class RuntimeVersionConflict(Exception):
    pass


def _error(status: int, code: str = "runtime.protocol_error") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"contractVersion": 1, "code": code},
    )


class RuntimeProtocolExceptionHandlers:
    @staticmethod
    def install(app: FastAPI) -> None:
        @app.exception_handler(RequestValidationError)
        async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
            return _error(400)

        @app.exception_handler(RuntimeProtocolViolation)
        async def protocol_error(_: Request, __: RuntimeProtocolViolation) -> JSONResponse:
            return _error(400)

        @app.exception_handler(RuntimeVersionConflict)
        async def version_conflict(_: Request, __: RuntimeVersionConflict) -> JSONResponse:
            return _error(409)

        @app.exception_handler(RequestBodyTooLarge)
        async def body_too_large(_: Request, __: RequestBodyTooLarge) -> JSONResponse:
            return _error(413)

        @app.exception_handler(RuntimeCapacityExceeded)
        async def capacity_exceeded(_: Request, __: RuntimeCapacityExceeded) -> JSONResponse:
            return _error(429)

        @app.exception_handler(Exception)
        async def unknown_error(_: Request, __: Exception) -> JSONResponse:
            return _error(500, "runtime.internal_error")
