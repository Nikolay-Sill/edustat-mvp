"""Общие фикстуры тестов.

Тестовая база edustat_test пересоздаётся один раз за запуск pytest и проходит те же миграции
db/migrations, что и рабочая: тесты проверяют настоящую схему, а не create_all из ORM.
Каждый тест работает внутри транзакции, которая откатывается в конце, так что тесты
не влияют друг на друга.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
OPENAPI_PATH = REPO_ROOT / "docs" / "specs" / "edustat-openapi.yaml"


def migration_files() -> list[Path]:
    """V1__…, V2__…, … по номеру версии (V10 после V9, а не после V1)."""
    files = MIGRATIONS_DIR.glob("V*__*.sql")
    return sorted(files, key=lambda p: int(re.match(r"V(\d+)__", p.name).group(1)))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = make_url(get_settings().test_database_url)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as exc:
        pytest.exit(f"Нет подключения к PostgreSQL ({url.host}:{url.port}). "
                    f"Запустите: docker compose up -d db\n{exc}", returncode=2)
    finally:
        admin.dispose()

    test_engine = create_engine(url)
    with test_engine.begin() as conn:
        for path in migration_files():
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Сессия в транзакции с откатом. commit() внутри кода фиксирует только SAVEPOINT."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint",
                      expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db: Session) -> dict[str, int]:
    """Справочники из scripts/seed.py (4 группы, 5 дисциплин, 30 демо-студентов)."""
    from scripts.seed import seed

    return seed(db)
