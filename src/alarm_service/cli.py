"""Command-line entry point for explicit alarm imports."""

import argparse
import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from alarm_service.domain.catalog import SOURCE_SYSTEM
from alarm_service.infrastructure.database.import_runner import ImportFailed, run_import
from alarm_service.infrastructure.database.session import build_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-system", default=SOURCE_SYSTEM)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    engine = build_engine()
    try:
        summary = run_import(
            engine, args.input, source_system=args.source_system, batch_size=args.batch_size
        )
    except ImportFailed as exc:
        parser.exit(1, f"{exc}\n")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot start import: {exc}\n")
    except SQLAlchemyError:
        parser.exit(
            1, "Database operation failed; check connectivity, migrations, and catalog loading.\n"
        )
    finally:
        engine.dispose()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
