"""Streaming legacy CSV adapter with explicit file and row shape handling."""

import csv
from collections.abc import Iterator
from pathlib import Path

from alarm_service.domain.catalog import CSV_FIELDS


class CsvSourceError(ValueError):
    """The file cannot be read under the declared CSV contract."""


def iter_csv_records(path: Path) -> Iterator[tuple[int, dict]]:
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)
            if header is None or len(header) != len(CSV_FIELDS) or set(header) != set(CSV_FIELDS):
                raise CsvSourceError("CSV header must contain each expected column exactly once.")
            for number, values in enumerate(reader, start=1):
                record = dict(zip(header, values, strict=False))
                if len(values) > len(header):
                    record["__extra_fields__"] = values[len(header) :]
                yield number, record
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CsvSourceError(f"Cannot read CSV source: {exc}") from exc
