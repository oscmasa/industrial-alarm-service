"""CLI for generating the synthetic industrial alarm export."""

import argparse
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from alarm_service.infrastructure.files.synthetic import generate_dataset


def rate(value: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("rate must be a decimal between 0 and 1") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--start-id",
        type=int,
        default=1,
        help="First event number (1-99999999); use a disjoint range for another export.",
    )
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 9, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 1))
    parser.add_argument("--recoverable-rate", type=rate, default=Decimal("0.10"))
    parser.add_argument("--invalid-rate", type=rate, default=Decimal("0.03"))
    parser.add_argument("--duplicate-rate", type=rate, default=Decimal("0.02"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets/raw/alarms.csv",
    )
    args = parser.parse_args()
    try:
        summary = generate_dataset(
            args.output,
            rows=args.rows,
            seed=args.seed,
            start_id=args.start_id,
            start=args.start,
            end=args.end,
            recoverable_rate=args.recoverable_rate,
            invalid_rate=args.invalid_rate,
            duplicate_rate=args.duplicate_rate,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
