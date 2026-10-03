"""Configured signal metadata and its compatible alarm types."""

from pydantic import BaseModel


class SignalItem(BaseModel):
    tag: str
    equipment_name: str
    unit: str
    alarm_types: list[str]


class SignalCatalogResponse(BaseModel):
    catalog_version: str
    items: list[SignalItem]
