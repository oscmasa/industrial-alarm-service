"""Aggregated metrics for accepted historical alarm events."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from alarm_service.api.dependencies import get_alarm_metrics_store, get_overview_store
from alarm_service.api.schemas.metrics import TopTagItem, TopTagsFilters, TopTagsResponse
from alarm_service.api.schemas.overview import (
    AvailableDatesResponse,
    OverviewFilters,
    OverviewResponse,
)
from alarm_service.application.ports.alarm_metrics import AlarmMetricsStore, TopTagsQuery
from alarm_service.application.ports.overview import OverviewQuery, OverviewStore
from alarm_service.application.use_cases.overview import build_overview
from alarm_service.application.use_cases.top_tags import top_tags

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("/available-dates", response_model=AvailableDatesResponse)
def get_available_dates(
    store: Annotated[OverviewStore, Depends(get_overview_store)],
) -> AvailableDatesResponse:
    dates = store.available_dates()
    return AvailableDatesResponse(first_event=dates.first_event, last_event=dates.last_event)


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    filters: Annotated[OverviewFilters, Query()],
    store: Annotated[OverviewStore, Depends(get_overview_store)],
) -> OverviewResponse:
    query = OverviewQuery(**filters.model_dump())
    return OverviewResponse(**build_overview(query, store.overview(query)))


@router.get("/top-tags", response_model=TopTagsResponse)
def get_top_tags(
    filters: Annotated[TopTagsFilters, Query()],
    store: Annotated[AlarmMetricsStore, Depends(get_alarm_metrics_store)],
) -> TopTagsResponse:
    items = top_tags(TopTagsQuery(**filters.model_dump()), store)
    return TopTagsResponse(
        items=[TopTagItem(tag=item.tag, event_count=item.event_count) for item in items],
        limit=filters.limit,
    )
