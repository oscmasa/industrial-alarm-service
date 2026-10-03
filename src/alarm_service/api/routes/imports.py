"""Read-only import history and original rejected records."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from alarm_service.api.dependencies import get_data_quality_store
from alarm_service.api.schemas.alarms import Pagination
from alarm_service.api.schemas.data_quality import (
    ImportItem,
    ImportListResponse,
    QualityFilters,
    RejectionFilters,
    RejectionItem,
    RejectionListResponse,
)
from alarm_service.application.ports.data_quality import DataQualityStore

router = APIRouter(prefix="/api/imports", tags=["Data quality"])


def pagination(filters: QualityFilters, total: int) -> Pagination:
    return Pagination(
        page=filters.page, page_size=filters.page_size, total=total,
        total_pages=(total + filters.page_size - 1) // filters.page_size,
    )


@router.get("", response_model=ImportListResponse)
def list_imports(
    filters: Annotated[QualityFilters, Query()],
    store: Annotated[DataQualityStore, Depends(get_data_quality_store)],
) -> ImportListResponse:
    result = store.list_imports(filters.page, filters.page_size)
    return ImportListResponse(
        items=[ImportItem.model_validate(item) for item in result.items],
        pagination=pagination(filters, result.total),
    )


@router.get("/{import_id}/rejections", response_model=RejectionListResponse)
def list_rejections(
    import_id: UUID,
    filters: Annotated[RejectionFilters, Query()],
    store: Annotated[DataQualityStore, Depends(get_data_quality_store)],
) -> RejectionListResponse:
    result = store.list_rejections(
        import_id, filters.page, filters.page_size, filters.error_code
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Import not found.")
    return RejectionListResponse(
        import_id=import_id,
        items=[RejectionItem.model_validate(item) for item in result.items],
        pagination=pagination(filters, result.total),
    )
