"""Aggregated metrics for accepted historical alarm events."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from alarm_service.api.dependencies import get_alarm_metrics_store
from alarm_service.api.schemas.metrics import TopTagItem, TopTagsFilters, TopTagsResponse
from alarm_service.application.ports.alarm_metrics import AlarmMetricsStore, TopTagsQuery
from alarm_service.application.use_cases.top_tags import top_tags

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


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
