"""Top-tag aggregation input and response contracts."""

from pydantic import BaseModel, Field

from alarm_service.api.schemas.event_filters import EventFilters


class TopTagsFilters(EventFilters):
    limit: int = Field(default=10, ge=1, le=100)


class TopTagItem(BaseModel):
    tag: str
    event_count: int


class TopTagsResponse(BaseModel):
    items: list[TopTagItem]
    limit: int
