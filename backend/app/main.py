"""Точка входа EduStat API (модульный монолит). Запуск: uvicorn app.main:app --reload"""

import logging

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.academic.router import router as academic_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(
        title="EduStat API",
        version="1.0.0",
        description="MVP-прототип. Контракт — docs/specs/edustat-openapi.yaml. "
                    "Ошибки — в формате RFC 7807 (application/problem+json).",
        docs_url="/docs",
    )
    register_error_handlers(app)
    app.include_router(academic_router, prefix=settings.api_prefix)
    app.openapi = lambda: _openapi_without_422(app)
    return app


def _openapi_without_422(app: FastAPI) -> dict:
    """FastAPI сам дописывает в документацию ответ 422, но ошибки валидации мы отдаём как 400
    (responses/BadRequest в спецификации). Убираем 422, чтобы Swagger UI не расходился с контрактом."""
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, description=app.description,
                             routes=app.routes)
        for path_item in schema["paths"].values():
            for operation in path_item.values():
                operation.get("responses", {}).pop("422", None)
        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)
        app.openapi_schema = schema
    return app.openapi_schema


app = create_app()
