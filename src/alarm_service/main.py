"""Application composition and ASGI entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from alarm_service.api.routes.alarms import router as alarms_router
from alarm_service.api.routes.catalog import router as catalog_router
from alarm_service.api.routes.imports import router as imports_router
from alarm_service.api.routes.metrics import router as metrics_router
from alarm_service.api.routes.status import router as status_router
from alarm_service.config import Settings, get_settings
from alarm_service.infrastructure.database.session import build_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.database_engine = build_engine(configuration)
        try:
            yield
        finally:
            app.state.database_engine.dispose()

    application = FastAPI(
        lifespan=lifespan,
        title=configuration.app_name,
        version=configuration.app_version,
        docs_url="/docs" if configuration.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if configuration.docs_enabled else None,
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database operation unavailable. Please retry later."},
        )

    application.include_router(alarms_router)
    application.include_router(catalog_router)
    application.include_router(imports_router)
    application.include_router(metrics_router)
    application.include_router(status_router)
    return application


app = create_app()
