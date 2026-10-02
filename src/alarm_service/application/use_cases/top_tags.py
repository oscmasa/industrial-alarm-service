"""Return the tags with the most accepted activations in a period."""

from alarm_service.application.ports.alarm_metrics import AlarmMetricsStore, TagCount, TopTagsQuery


def top_tags(query: TopTagsQuery, store: AlarmMetricsStore) -> list[TagCount]:
    if not 1 <= query.limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    for timestamp in (query.start_time, query.end_time):
        if timestamp is not None and (timestamp.tzinfo is None or timestamp.utcoffset() is None):
            raise ValueError("Time filters must have a timezone")
    if query.start_time and query.end_time and query.start_time >= query.end_time:
        raise ValueError("start_time must be before end_time")
    return store.top_tags(query)
