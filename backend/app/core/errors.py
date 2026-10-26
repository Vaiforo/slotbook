import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            error=ErrorDetail(
                code=code,
                message=message,
                request_id=request.state.request_id,
            )
        ).model_dump(),
    )


def install_error_handling(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}
        response = error_response(
            request,
            exc.status_code,
            codes.get(exc.status_code, "http_error"),
            HTTPStatus(exc.status_code).phrase,
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo input, tokens, or validation context into a public error.
        return error_response(request, 422, "validation_error", "Проверьте параметры запроса.")

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # No exception string/trace: DB errors may include bound private values.
            response = error_response(request, 500, "internal_error", "Внутренняя ошибка сервера.")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        route = request.scope.get("route")
        logger.log(
            logging.ERROR if response.status_code >= 500 else logging.INFO,
            "HTTP request",
            extra={
                "request_id": request.state.request_id,
                "route": getattr(route, "path", "<unmatched>"),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response
