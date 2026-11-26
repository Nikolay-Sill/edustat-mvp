"""Контрактные тесты: ответы API проверяются JSON-схемами из docs/specs/edustat-openapi.yaml.

Спецификация — источник истины, поэтому схемы берутся прямо из неё, а не копируются в тесты:
если поле переименуют в спецификации или в коде, тест упадёт.
"""

from functools import cache

import pytest
import yaml
from openapi_schema_validator import OAS30Validator
from sqlalchemy import select

from app.academic.models import Student
from app.main import app
from tests.conftest import OPENAPI_PATH

API = "/api/v1"


@cache
def spec() -> dict:
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


def _inline_refs(node):
    """Подставляет $ref на components, чтобы валидатору не нужен был resolver."""
    if isinstance(node, dict):
        if "$ref" in node:
            target = spec()
            for part in node["$ref"].removeprefix("#/").split("/"):
                target = target[part]
            return _inline_refs(target)
        return {key: _inline_refs(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item) for item in node]
    return node


def response_schema(path: str, status: str, media_type: str = "application/json") -> dict:
    response = _inline_refs(spec()["paths"][path]["get"]["responses"][status])
    return response["content"][media_type]["schema"]


def assert_matches(instance, schema) -> None:
    OAS30Validator(schema).validate(instance)


def test_app_implements_academic_operations_from_spec():
    """FR-05: пути и operationId справочника совпадают со спецификацией."""
    ours = app.openapi()["paths"]
    for path, operation_id in [("/groups", "listGroups"), ("/students", "listStudents"),
                               ("/students/{student_id}", "getStudent"), ("/subjects", "listSubjects")]:
        assert spec()["paths"][path]["get"]["operationId"] == operation_id
        assert ours[API + path]["get"]["operationId"] == operation_id
        # Ошибки валидации — 400, как в спецификации; 422 FastAPI в документации быть не должно
        assert "422" not in ours[API + path]["get"]["responses"]


def test_swagger_schema_names_match_spec():
    """FR-05: схемы ответов в Swagger UI называются как в спецификации."""
    ours = app.openapi()["components"]["schemas"]
    assert {"Group", "Student", "Subject", "Problem"} <= set(ours)
    assert "HTTPValidationError" not in ours


@pytest.mark.parametrize("path", ["/groups", "/students", "/subjects"])
def test_list_responses_match_spec(client, seeded, path):
    """FR-05: ответы списков соответствуют схемам Group/Student/Subject и PageMeta."""
    response = client.get(API + path)

    assert response.status_code == 200
    assert response.json()["items"], "проверка по пустому списку ничего не доказывает"
    assert_matches(response.json(), response_schema(path, "200"))


def test_student_card_matches_spec(client, db, seeded):
    """FR-05: карточка студента соответствует схеме Student — и с датой рождения, и без неё."""
    schema = response_schema("/students/{student_id}", "200")
    with_birth = db.scalars(select(Student).where(Student.birth_date.is_not(None))).first()
    without_birth = db.scalars(select(Student).where(Student.birth_date.is_(None))).first()

    for student in (with_birth, without_birth):
        assert_matches(client.get(f"{API}/students/{student.student_id}").json(), schema)


@pytest.mark.parametrize(("url", "path", "status"), [
    (f"{API}/students/999999", "/students/{student_id}", "404"),
    (f"{API}/students?page=0", "/students", "400"),
])
def test_errors_match_problem_schema(client, url, path, status):
    """FR-05: ошибки соответствуют схеме Problem (RFC 7807) и media type application/problem+json."""
    response = client.get(url)

    assert str(response.status_code) == status
    assert_matches(response.json(), response_schema(path, status, "application/problem+json"))
