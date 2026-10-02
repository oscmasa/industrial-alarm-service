"""Alarm listing use case independent of HTTP and database drivers."""

from alarm_service.application.ports.alarm_query import AlarmPage, AlarmQuery, AlarmQueryStore


def query_alarms(query: AlarmQuery, store: AlarmQueryStore) -> AlarmPage:
    if not 1 <= query.page <= 100000 or not 1 <= query.page_size <= 100:
        raise ValueError("Invalid pagination")
    for timestamp in (query.start_time, query.end_time):
        if timestamp is not None and (timestamp.tzinfo is None or timestamp.utcoffset() is None):
            raise ValueError("Time filters must have a timezone")
    if query.start_time and query.end_time and query.start_time >= query.end_time:
        raise ValueError("start_time must be before end_time")
    return store.list_alarms(query)
