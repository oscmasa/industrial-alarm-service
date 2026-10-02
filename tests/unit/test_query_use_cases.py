"""Application entry points protect their time filters independently of HTTP."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from alarm_service.application.ports.alarm_metrics import TopTagsQuery
from alarm_service.application.ports.alarm_query import AlarmQuery
from alarm_service.application.use_cases.query_alarms import query_alarms
from alarm_service.application.use_cases.top_tags import top_tags

INSTANT = datetime(2026, 9, 15, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "query_type,execute,method",
    [(AlarmQuery, query_alarms, "list_alarms"), (TopTagsQuery, top_tags, "top_tags")],
)
@pytest.mark.parametrize(
    "start,end",
    [
        (INSTANT.replace(tzinfo=None), None),
        (None, INSTANT.replace(tzinfo=None)),
        (INSTANT, INSTANT),
        (INSTANT, INSTANT - timedelta(seconds=1)),
        (INSTANT, INSTANT.astimezone(timezone(timedelta(hours=-5)))),
    ],
)
def test_invalid_time_ranges_never_reach_store(query_type, execute, method, start, end):
    store = Mock()
    with pytest.raises(ValueError):
        execute(query_type(start_time=start, end_time=end), store)
    getattr(store, method).assert_not_called()


@pytest.mark.parametrize(
    "query_type,execute,method",
    [(AlarmQuery, query_alarms, "list_alarms"), (TopTagsQuery, top_tags, "top_tags")],
)
@pytest.mark.parametrize(
    "start,end",
    [
        (None, None),
        (INSTANT, None),
        (None, INSTANT),
        (INSTANT, (INSTANT + timedelta(seconds=1)).astimezone(timezone(timedelta(hours=-5)))),
    ],
)
def test_valid_ranges_delegate_to_store(query_type, execute, method, start, end):
    store = Mock()
    query = query_type(start_time=start, end_time=end)
    result = execute(query, store)
    assert result is getattr(store, method).return_value
    getattr(store, method).assert_called_once_with(query)
