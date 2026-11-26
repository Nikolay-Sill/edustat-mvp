"""Подключение к PostgreSQL через SQLAlchemy 2 (синхронный режим, драйвер psycopg 3).

Схема БД создаётся только миграциями db/migrations (V1, V2, …).
ORM-модели лишь описывают уже существующие таблицы — Base.metadata.create_all не вызывается.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping: не отдавать «мёртвые» соединения после перезапуска контейнера с БД
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос, закрывается после ответа."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
