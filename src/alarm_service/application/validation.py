"""Time-range rules shared by application use cases."""

from datetime import datetime


def validate_time_range(start_time: datetime | None, end_time: datetime | None) -> None:
    for timestamp in (start_time, end_time):
        if timestamp is not None and (timestamp.tzinfo is None or timestamp.utcoffset() is None):
            raise ValueError("Time filters must have a timezone")
    if start_time is not None and end_time is not None and start_time >= end_time:
        raise ValueError("start_time must be before end_time")
