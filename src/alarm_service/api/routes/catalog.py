"""Configured tags and compatible alarm types for dependent selectors."""

from fastapi import APIRouter

from alarm_service.api.schemas.catalog import SignalCatalogResponse, SignalItem
from alarm_service.application.use_cases.signal_catalog import signal_catalog
from alarm_service.domain.catalog import CATALOG_VERSION

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


@router.get("/tags", response_model=SignalCatalogResponse)
def get_signal_catalog() -> SignalCatalogResponse:
    return SignalCatalogResponse(
        catalog_version=CATALOG_VERSION,
        items=[
            SignalItem(
                tag=item.tag,
                equipment_name=item.equipment_name,
                unit=item.unit,
                alarm_types=list(item.alarm_types),
            )
            for item in signal_catalog()
        ],
    )
