"""Единый формат ошибок по RFC 7807 (application/problem+json) со сквозным trace_id.

Каждый запрос получает trace_id: он попадает в лог, в заголовок X-Trace-Id и в тело ошибки,
чтобы по сообщению пользователя можно было найти запись в логах (схема Problem в OpenAPI).
"""

import logging
import uuid
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("edustat")

PROBLEM_MEDIA_TYPE = "application/problem+json"
ERROR_TYPE_BASE = "https://edustat.example.ru/errors/"
TRACE_HEADER = "X-Trace-Id"

# Код ответа → «тип» ошибки (URI из примера BadRequest в спецификации)
_ERROR_TYPES = {
    400: "validation",
    401: "unauthorized",
    403: "forbidden",
    404: "not-found",
    405: "method-not-allowed",
    409: "conflict",
    500: "internal",
}


class ProblemException(Exception):
    """Исключение предметной логики, которое превращается в ответ RFC 7807."""

    def __init__(self, status: int, detail: str | None = None, title: str | None = None):
        self.status = status
        self.detail = detail
        self.title = title
        super().__init__(detail or title)


def new_trace_id() -> str:
    # 16 hex-символов, как в примере спецификации (4bf92f3577b34da6)
    return uuid.uuid4().hex[:16]


def problem_response(
    request: Request, status: int, detail: str | None = None, title: str | None = None
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or new_trace_id()
    body = {
        "type": ERROR_TYPE_BASE + _ERROR_TYPES.get(status, "error"),
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "instance": request.url.path,
        "trace_id": trace_id,
    }
    if detail:
        body["detail"] = detail
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE,
                        headers={TRACE_HEADER: trace_id})


def _format_validation_errors(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        # loc выглядит как ("query", "page") — источник параметра пользователю не нужен
        field = ".".join(str(p) for p in err["loc"] if p not in ("query", "path", "body"))
        parts.append(f"{field}: {err['msg']}" if field else err["msg"])
    return "; ".join(parts)


def register_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        request.state.trace_id = new_trace_id()
        try:
            response = await call_next(request)
        except Exception:
            # Непредвиденная ошибка: подробности — только в лог, клиенту — trace_id
            logger.exception("Необработанная ошибка, trace_id=%s", request.state.trace_id)
            return problem_response(request, 500, detail="Внутренняя ошибка сервера")
        response.headers[TRACE_HEADER] = request.state.trace_id
        return response

    @app.exception_handler(ProblemException)
    async def handle_problem(request: Request, exc: ProblemException):
        return problem_response(request, exc.status, exc.detail, exc.title)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        # FastAPI по умолчанию отвечает 422, а спецификация требует 400 (responses/BadRequest)
        return problem_response(request, 400, _format_validation_errors(exc), "Validation error")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        # Сюда попадают, например, 404 на несуществующий путь и 405 на неверный метод
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != HTTPStatus(
            exc.status_code).phrase else None
        return problem_response(request, exc.status_code, detail)
