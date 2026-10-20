"""Single error envelope: {"error": {"code", "message_key", "params"}} (HANDOFF §7)."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, status: int, code: str, params: dict[str, Any] | None = None):
        self.status = status
        self.code = code
        self.params = params or {}


def envelope(code: str, params: dict[str, Any] | None = None) -> dict:
    return {"error": {"code": code, "message_key": f"errors.{code}", "params": params or {}}}


_HTTP_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    501: "not_implemented",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(envelope(exc.code, exc.params), status_code=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "error")
        return JSONResponse(envelope(code), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"loc": [str(p) for p in e["loc"]], "type": e["type"], "msg": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(envelope("validation_failed", {"fields": fields}), status_code=422)
