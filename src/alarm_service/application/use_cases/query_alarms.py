"""Alarm listing use case independent of HTTP and database drivers."""

from alarm_service.application.ports.alarm_query import AlarmPage, AlarmQuery, AlarmQueryStore
from alarm_service.application.validation import validate_time_range


def query_alarms(query: AlarmQuery, store: AlarmQueryStore) -> AlarmPage:
    if not 1 <= query.page <= 100000 or not 1 <= query.page_size <= 100:
        raise ValueError("Invalid pagination")
    validate_time_range(query.start_time, query.end_time)
    return store.list_alarms(query)
