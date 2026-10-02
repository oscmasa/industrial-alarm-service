"""Preview normalization outcomes without database writes or deduplication."""

import argparse
import json
from collections import Counter
from pathlib import Path

from alarm_service.application.normalization.service import normalize_record
from alarm_service.infrastructure.files.csv_reader import CsvSourceError, iter_csv_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets/raw/alarms.csv",
    )
    args = parser.parse_args()
    counts = Counter(
        records_read=0, accepted_rows=0, rejected_rows=0, accepted_rows_with_warnings=0
    )
    errors, warnings = Counter(), Counter()
    try:
        for _, record in iter_csv_records(args.input):
            result = normalize_record(record)
            counts["records_read"] += 1
            counts["accepted_rows" if result.accepted else "rejected_rows"] += 1
            errors.update(issue.code for issue in result.errors)
            if result.accepted:
                warnings.update(issue.code for issue in result.warnings)
                counts["accepted_rows_with_warnings"] += bool(result.warnings)
    except CsvSourceError as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                **counts,
                "error_counts": dict(errors),
                "warning_counts": dict(warnings),
                "deduplication_applied": False,
                "database_writes": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
