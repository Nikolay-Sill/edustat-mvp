"""Формат ошибок RFC 7807, trace_id и проверка параметров пагинации."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

API = "/api/v1"


@pytest.mark.parametrize("url", [
    f"{API}/groups?page=0",
    f"{API}/groups?size=0",
    f"{API}/groups?size=101",
    f"{API}/groups?course=7",
    f"{API}/students?page=abc",
    f"{API}/students/abc",
])
def test_invalid_params_return_400_problem(client, url):
    """FR-05: неверные параметры — 400 (не 422 FastAPI) в формате RFC 7807."""
    response = client.get(url)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["title"] == "Validation error"
    assert body["type"] == "https://edustat.example.ru/errors/validation"
    assert body["detail"]


def test_problem_has_trace_id_and_instance(client):
    """FR-05: trace_id в теле ошибки совпадает с заголовком X-Trace-Id, instance — путь запроса."""
    response = client.get(f"{API}/groups?page=0")

    body = response.json()
    assert body["trace_id"] == response.headers["X-Trace-Id"]
    assert len(body["trace_id"]) == 16
    assert body["instance"] == f"{API}/groups"


def test_successful_response_has_trace_header(client):
    """FR-05: trace_id есть и в успешных ответах — для поиска запроса в логах."""
    assert client.get(f"{API}/groups").headers["X-Trace-Id"]


def test_unknown_path_returns_404_problem(client):
    """FR-05: несуществующий путь — 404 в формате RFC 7807."""
    response = client.get(f"{API}/no-such-path")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_unexpected_error_returns_500_problem_without_internals():
    """FR-05: непредвиденная ошибка — 500 в формате RFC 7807 без текста исключения."""
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("секретная деталь")

    response = TestClient(app).get("/boom")

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert "секретная деталь" not in response.text
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"]
