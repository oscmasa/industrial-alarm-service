"""Application composition and ASGI entry point."""

from fastapi import FastAPI

from alarm_service.api.routes.status import router as status_router
from alarm_service.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else get_settings()
    application = FastAPI(
        title=configuration.app_name,
        version=configuration.app_version,
        docs_url="/docs" if configuration.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if configuration.docs_enabled else None,
    )
    application.include_router(status_router)
    return application


app = create_app()
