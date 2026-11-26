"""Общие схемы API: Problem (RFC 7807) для описания ошибок в Swagger UI."""

from pydantic import BaseModel


class Problem(BaseModel):
    type: str | None = None
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    trace_id: str | None = None


_DESCRIPTIONS = {
    400: "Ошибка в параметрах запроса",
    401: "Токен отсутствует или истёк",
    403: "Недостаточно прав для ресурса",
    404: "Ресурс не найден",
}


def PROBLEM_RESPONSES(*codes: int) -> dict:  # noqa: N802 — читается как константа в декораторе
    """Описание ответов-ошибок для декоратора роутера (видно в Swagger UI)."""
    return {
        code: {"model": Problem, "description": _DESCRIPTIONS[code],
               "content": {"application/problem+json": {}}}
        for code in codes
    }
