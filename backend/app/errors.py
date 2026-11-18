"""统一错误格式 {code, message, details}，对应 docs/API.md。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import ErrorCode, ErrorResponse

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: ErrorCode, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details


def _json(status: int, code: ErrorCode, message: str, details: dict | None = None) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=details).model_dump()
    return JSONResponse(status_code=status, content=body)


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return _json(e.status, e.code, e.message, e.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        fields = [{"field": ".".join(str(x) for x in err["loc"][1:]), "message": err["msg"]} for err in e.errors()]
        return _json(422, "VALIDATION_ERROR", "请求参数不合法", {"fields": fields})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, e: Exception):
        log.exception("unhandled error")
        return _json(500, "INTERNAL_ERROR", "服务器内部错误")


NOT_FOUND = lambda: ApiError(404, "DISCUSSION_NOT_FOUND", "讨论不存在")  # noqa: E731
