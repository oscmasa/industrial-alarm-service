"""Paginated access to accepted historical alarms."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from alarm_service.api.dependencies import get_alarm_query_store
from alarm_service.api.schemas.alarms import AlarmFilters, AlarmItem, AlarmListResponse, Pagination
from alarm_service.application.ports.alarm_query import AlarmQuery, AlarmQueryStore
from alarm_service.application.use_cases.query_alarms import query_alarms

router = APIRouter(prefix="/api/alarms", tags=["Alarms"])


@router.get("", response_model=AlarmListResponse)
def list_alarms(
    filters: Annotated[AlarmFilters, Query()],
    store: Annotated[AlarmQueryStore, Depends(get_alarm_query_store)],
) -> AlarmListResponse:
    page = query_alarms(AlarmQuery(**filters.model_dump()), store)
    return AlarmListResponse(
        items=[
            AlarmItem(
                id=record.id,
                source_system=record.source_system,
                import_id=record.import_id,
                unit=record.unit,
                **{key: value for key, value in vars(record.alarm).items()},
            )
            for record in page.items
        ],
        pagination=Pagination(
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            total_pages=(page.total + page.page_size - 1) // page.page_size,
        ),
    )
