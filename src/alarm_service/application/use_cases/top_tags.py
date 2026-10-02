"""Return the tags with the most accepted activations in a period."""

from alarm_service.application.ports.alarm_metrics import AlarmMetricsStore, TagCount, TopTagsQuery
from alarm_service.application.validation import validate_time_range


def top_tags(query: TopTagsQuery, store: AlarmMetricsStore) -> list[TagCount]:
    if not 1 <= query.limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    validate_time_range(query.start_time, query.end_time)
    return store.top_tags(query)
