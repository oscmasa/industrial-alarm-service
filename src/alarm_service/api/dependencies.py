"""HTTP composition dependencies; database engines belong to app lifespan."""

from fastapi import Request

from alarm_service.application.ports.alarm_metrics import AlarmMetricsStore
from alarm_service.application.ports.alarm_query import AlarmQueryStore
from alarm_service.application.ports.data_quality import DataQualityStore
from alarm_service.application.ports.overview import OverviewStore
from alarm_service.infrastructure.database.alarm_metrics import PostgresAlarmMetrics
from alarm_service.infrastructure.database.alarm_query import PostgresAlarmQuery
from alarm_service.infrastructure.database.data_quality import PostgresDataQuality
from alarm_service.infrastructure.database.overview import PostgresOverview


def get_alarm_query_store(request: Request) -> AlarmQueryStore:
    return PostgresAlarmQuery(request.app.state.database_engine)


def get_alarm_metrics_store(request: Request) -> AlarmMetricsStore:
    return PostgresAlarmMetrics(request.app.state.database_engine)


def get_overview_store(request: Request) -> OverviewStore:
    return PostgresOverview(request.app.state.database_engine)


def get_data_quality_store(request: Request) -> DataQualityStore:
    return PostgresDataQuality(request.app.state.database_engine)
