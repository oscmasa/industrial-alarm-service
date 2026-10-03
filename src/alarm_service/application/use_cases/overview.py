"""Compute bounded daily metrics from database aggregates, never event rows."""

from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from alarm_service.application.ports.overview import OverviewQuery, OverviewSnapshot
from alarm_service.domain.alarm import Severity

PLANT_ZONE = ZoneInfo("America/Bogota")


def build_overview(query: OverviewQuery, snapshot: OverviewSnapshot) -> dict:
    start = query.start_time.astimezone(PLANT_ZONE).date()
    end = query.end_time.astimezone(PLANT_ZONE).date()
    length = (end - start).days
    previous_start = start - timedelta(days=length)
    first = snapshot.dates.first_event
    last = snapshot.dates.last_event
    first_day = first.astimezone(PLANT_ZONE).date() if first else None
    last_day = last.astimezone(PLANT_ZONE).date() if last else None
    by_day = {}
    severity_counts = {severity.value: 0 for severity in Severity}
    previous_count = 0
    for row in snapshot.counts:
        by_day[row.day] = by_day.get(row.day, 0) + row.event_count
        if start <= row.day < end:
            severity_counts[row.severity] += row.event_count
        elif previous_start <= row.day < start:
            previous_count += row.event_count
    daily = []
    for offset in range(length):
        day = start + timedelta(days=offset)
        # Outside observed dates, absence of events is not an observed zero day.
        eligible = first_day is not None and first_day <= day - timedelta(days=6)
        eligible = eligible and last_day is not None and day <= last_day
        average = None
        if eligible:
            average = Decimal(sum(by_day.get(day - timedelta(days=i), 0) for i in range(7))) / 7
            average = average.quantize(Decimal("0.01"))
        daily.append(
            {"date": day, "event_count": by_day.get(day, 0), "moving_average_7_days": average}
        )
    total = sum(severity_counts.values())
    comparable = (
        first_day is not None
        and last_day is not None
        and first_day <= previous_start
        and last_day >= end - timedelta(days=1)
    )
    change = None
    if comparable and previous_count:
        change = (Decimal(total - previous_count) * 100 / previous_count).quantize(Decimal("0.01"))
    reason = (
        "outside_observed_dates"
        if not comparable
        else ("zero_baseline" if previous_count == 0 else None)
    )
    return {
        "timezone": "America/Bogota",
        "start_time": query.start_time,
        "end_time": query.end_time,
        "severity": query.severity,
        "tag": query.tag,
        "alarm_code": query.alarm_code,
        "total_events": total,
        "severity_counts": severity_counts,
        "daily": daily,
        "comparison": {
            "start_time": query.start_time - timedelta(days=length),
            "end_time": query.start_time,
            "event_count": previous_count if comparable else None,
            "change_percent": change,
            "unavailable_reason": reason,
        },
    }
