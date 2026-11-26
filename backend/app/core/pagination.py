"""Пагинация page/size по параметрам Page, Size и схеме PageMeta из edustat-openapi.yaml."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: int = Query(1, ge=1, description="Номер страницы, начиная с 1"),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Размер страницы"),
) -> PageParams:
    """Зависимость FastAPI: проверяет page и size, при ошибке — 400 в формате RFC 7807."""
    return PageParams(page=page, size=size)


class Page[T](BaseModel):
    """Ответ со списком: PageMeta + items (allOf в спецификации)."""

    items: list[T]
    page: int
    size: int
    total_elements: int
    total_pages: int


def paginate[T](session: Session, stmt: Select, params: PageParams, to_item: Callable[[Any], T]) -> Page[T]:
    """Выполняет запрос со смещением и считает общее число строк тем же запросом без сортировки."""
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = session.scalars(stmt.offset(params.offset).limit(params.size)).all()
    return Page[T](
        items=[to_item(row) for row in rows],
        page=params.page,
        size=params.size,
        total_elements=total,
        total_pages=math.ceil(total / params.size),
    )
