# Industrial Alarm Service

A Python service for importing, cleaning, normalizing, and querying
historical industrial alarm data through an API.

## Context

The dataset represents a fictional water treatment and bottling plant
with one production line and seven equipment units monitored by a
single SCADA system.

Each record represents an alarm activation.
The data is synthetic and intentionally includes data quality issues.

## Dataset Contract

See [the dataset contract](datasets/README.md) for the process diagram, equipment
catalog, field definitions, normalization rules, rejection policy, and generation plan.

## Generate Sample Data

```powershell
python -m pip install -e ".[dev]"
python scripts/generate_dataset.py --rows 10000 --seed 42
```

Outputs: `datasets/raw/alarms.csv` and `datasets/raw/alarms.manifest.json`.
The default dataset targets 9,500 accepted events, 300 rejected rows, and 200
duplicates. The manifest records generation expectations; it does not validate
an actual import. See the dataset contract for configurable rates and warnings.

## Preview Data Cleaning

```powershell
python scripts/check_dataset.py --input datasets/raw/alarms.csv
```

This streams the CSV and reports normalization errors and warnings without
writing to PostgreSQL. The default CSV yields 9,700 acceptable rows and 300
rejections. The 200 duplicate rows are still acceptable at this stage;
deduplication belongs to the next import stage. See the dataset contract for
numeric precision, field validation, and warning rules.

## Scope

- Reproducible CSV dataset generation.
- Data cleaning, validation, and normalization.
- Batch persistence in PostgreSQL.
- Import history and rejected record tracking.
- API with filtering, pagination, and aggregated metrics.
- Reproducible execution using Docker Compose.

## Architecture

The solution separates domain logic, application use cases,
infrastructure, and the API layer.

Application use cases access external integrations through ports.

## Project Status

The initial FastAPI service, environment configuration, and Docker Compose setup are implemented.
The dataset contract, industrial catalog, and reproducible CSV generator are implemented. Row normalization is implemented; atomic batch ingestion is implemented.

## Local Development Setup

Python 3.14 is required for the initial project configuration.

From the project root, activate the virtual environment and install the package:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Verify the package installation:

```powershell
python -c "import alarm_service; print('Package imported successfully')"
```

### Run the API

Optionally copy `.env.example` to `.env` to customize the service:

```powershell
Copy-Item .env.example .env
python -m uvicorn alarm_service.main:app --reload
```

- Status endpoint: http://127.0.0.1:8000/status
- Interactive API documentation: http://127.0.0.1:8000/docs
- OpenAPI schema: http://127.0.0.1:8000/openapi.json

`GET /status` returns `{"status": "ok"}`. This endpoint checks service
liveness only; database readiness will be implemented with persistence.

Configuration uses the `ALARM_` environment variable prefix. Environment
variables take precedence over `.env`. Set `ALARM_DOCS_ENABLED=false` to
disable Swagger and the OpenAPI endpoint. Keep `.env` out of version control.

### Development Checks

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Database models and the initial migration are implemented. Alarm ingestion, paginated queries, and top-tag aggregation are implemented.

## Docker Setup

With Docker Desktop running in Linux container mode, start the API and PostgreSQL:

```powershell
docker compose up --build -d --wait
```

No local Python installation or `.env` file is required. Optional configuration
is documented in `.env.example`. The default database credentials are intended
only for local development.

The API is available at http://127.0.0.1:8000/status and Swagger at
http://127.0.0.1:8000/docs. Stop any locally running Uvicorn server first, or
set `API_PORT=8001` in `.env` to use another port.

Check the services and view their logs:

```powershell
docker compose ps
docker compose logs api db
```

The API starts after PostgreSQL reports readiness. Its `/status` health check
verifies HTTP liveness; it does not query the database yet. PostgreSQL runs on
the internal Compose network and its port is not exposed to the host. The API
runs as a non-root user, without development auto-reload.

Stop and remove the containers while preserving database data:

```powershell
docker compose down
```

The `postgres_data` named volume persists across container recreation. Changing
database credentials in `.env` does not change an already initialized database.
`docker compose down -v` deletes the database volume and should only be used
when intentionally resetting local data.

## Query Alarms

`GET /api/alarms` lists accepted events only. Filters are optional and combine
with AND. Defaults: page 1, 50 items per page. Maximum page size: 100; maximum
page number: 100,000.

| Parameter | Meaning |
| --- | --- |
| start_time | Inclusive ISO 8601 instant with Z or explicit UTC offset |
| end_time | Exclusive ISO 8601 instant with Z or explicit UTC offset |
| severity | LOW, MEDIUM, HIGH, or CRITICAL; source aliases are not API values |
| tag | Exact tag, trimmed and normalized to uppercase |
| page | One-based page number |
| page_size | Number of items, from 1 to 100 |

Examples in PowerShell:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/alarms?page=1&page_size=10"
Invoke-RestMethod "http://127.0.0.1:8000/api/alarms?severity=HIGH&tag=PUMP_01_FLOW&page_size=10"
Invoke-RestMethod "http://127.0.0.1:8000/api/alarms?start_time=2026-09-15T00:00:00Z&end_time=2026-09-16T00:00:00Z"
```

Swagger at `/docs` also allows interactive filtering. When constructing URLs
manually, encode the plus sign in positive offsets as `%2B`; HTTP clients with
structured query parameters handle this automatically.

Responses have `items` and `pagination` containing `page`, `page_size`, `total`,
and `total_pages`. Items include internal ID, source event ID, source/import
references, UTC occurrence time, tag, condition, severity, message, value, and
warning codes. Decimal values are serialized as strings to preserve precision;
missing optional values are JSON nulls.

Events are ordered newest first, then internal ID descending to break timestamp
ties. No matches return 200 with an empty list and zero totals. A page beyond the
last page returns an empty list with the actual matching total. A syntactically
valid but unknown tag returns no matches rather than a validation error.

Invalid parameters, unsupported/naive timestamps, unknown query parameters, and
ranges with start >= end return 422. Database-operation failures return a generic
503 response without SQL, credentials, or tracebacks. `/status` still indicates
HTTP liveness only. Read queries use parameter binding, a 10-second statement
timeout, and a read-only repeatable-read transaction so page items and totals
share one snapshot. The application reuses an engine connection pool and disposes
it on shutdown; it does not connect merely to serve `/status`.

Offset pagination is appropriate for this dataset. Separate requests can observe
newly imported rows and therefore shift page boundaries. Cursor pagination and
alternative total-count strategies are future options for large histories.
The SQL adapter implements a read port called by the query use case; the HTTP
layer handles input/output contracts without embedding SQL.

## Top Alarm Tags

`GET /api/metrics/top-tags` ranks signals by their number of accepted alarm
activations. It supports `start_time`, `end_time`, and `severity` with the same
validation and inclusive-start/exclusive-end semantics as `/api/alarms`.
`limit` defaults to 10 and accepts values from 1 to 100.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/metrics/top-tags?limit=5"
Invoke-RestMethod "http://127.0.0.1:8000/api/metrics/top-tags?severity=HIGH&start_time=2026-09-01T05:00:00Z&end_time=2026-10-01T05:00:00Z&limit=5"
```

The second example selects September in the plant's UTC-05 timezone.
The response contains `items` with `tag` and `event_count`, plus the requested
`limit`. Counts include accepted events with warnings, exclude rejected rows,
and are not inflated by repeated imports. Counts combine all source systems
within the fixed plant catalog. Distinct activations with different event IDs
are counted separately.

Ranking uses event count descending, then tag ascending to resolve ties. The
response can contain fewer items than the limit; no matching events yield an
empty list with HTTP 200. Invalid filters return 422; database failures return
the same generic 503 as alarm queries. The aggregation is performed by PostgreSQL
using GROUP BY, COUNT, ORDER BY, and LIMIT, not by loading the full event history
into Python. It uses a read-only transaction and a 10-second statement timeout.
A count is not a duration, failure probability, or root-cause diagnosis.

## Import Alarm Data

Apply migrations and seed the catalog first (commands below). Rebuild the API
after code changes. Mount the source directory read-only in a temporary container:

```powershell
docker compose up --build -d --wait
docker compose run --rm -v "${PWD}/datasets/raw:/data:ro" api python -m alarm_service.cli --input /data/alarms.csv --batch-size 1000
```

The first import of the default dataset into a fresh alarm history must report:

- 10,000 records read.
- 9,500 accepted events, including 167 with warnings.
- 300 rejected rows and 200 duplicates.

Repeat the same command: it must insert zero new alarms, reject the same 300
invalid rows, and count 9,700 duplicates. Rejections are retained per import, so
two executions produce 600 rejection records while the alarm count stays 9,500.
Existing imports remain available as audit history.

Each import records a UUID, file name/checksum, source system, status, timestamps,
and counters. `--source-system` defaults to `SCADA_01`; choose the actual export
source deliberately because event uniqueness is scoped to it. `--batch-size`
accepts 1-5,000 rows. No generator manifest is consulted.

Processing uses bounded batches and bulk SQL inserts, with one existing-event
lookup per batch. Equal normalized events are skipped; an existing identifier
with different event fields is rejected as `DUPLICATE_CONFLICT`. Derived warning
codes and import metadata do not determine equality. Original events are not
updated on reimport.

All alarm and rejection batches belong to one transaction. A fatal file/database
error rolls them back and marks the separately created audit row `FAILED` while
the database remains reachable. Failed counters retain processed `records_read`
but zero accepted/rejected/duplicate counts, because nothing was persisted.
Successful counters reconcile. The file checksum is checked again before commit
to detect source changes during processing. Abrupt process termination can leave
a `RUNNING` audit row; automatic recovery is a future extension.

A PostgreSQL transaction-level advisory lock serializes imports for the same
source (30-second lock timeout). Different sources can proceed independently.
The database unique constraint remains the final safeguard. A large-file import
still uses one potentially long transaction; checkpointed imports would need
an explicit resumability design, rather than silently committing partial files.

Rejected originals containing NUL are stored losslessly as a JSON object with
`encoding=base64-json-utf8` and a `payload`, because PostgreSQL JSONB cannot hold
NUL. Other originals retain their normal field mapping.

To inspect the history with the default development credentials:

```powershell
docker compose exec db psql -U alarm_user -d alarms -c "SELECT status, records_read, accepted, rejected, duplicates, accepted_with_warnings FROM imports ORDER BY started_at; SELECT COUNT(*) AS alarm_count FROM alarms;"
```

## Database Schema and Migrations

The schema uses SQLAlchemy and versioned Alembic migrations. Database creation is
explicit; the API does not modify the schema on startup.

After rebuilding the containers, apply migrations and load the catalog:

```powershell
docker compose up --build -d --wait
docker compose exec api python -m alembic upgrade head
docker compose exec api python -m alarm_service.infrastructure.database.seed
docker compose exec api python -m alembic current
docker compose exec api python -m alembic check
```

`current` should report `0001_initial (head)`. `check` verifies model/schema
agreement. Running the seed command again inserts zero additional records.

| Table | Responsibility |
| --- | --- |
| equipment | Equipment identifiers and display names |
| tags | Signal identifiers, equipment references, and units |
| alarms | Accepted events, source identity, UTC timestamps, values, and warnings |
| imports | File checksum, execution state, timestamps, and reconciled counters |
| rejected_records | Original row fields and structured validation errors |

Alarm uniqueness is enforced by `(source_system, event_id)`. Historical records
are protected by foreign keys with restricted deletion. Composite indexes on
`(occurred_at, id)`, `(severity, occurred_at, id)`, and `(tag_id, occurred_at, id)`
support time filters and stable pagination. Extra indexes cover import and
equipment references. Index effectiveness must be checked against actual queries
as the API is implemented.

Timestamps use PostgreSQL `TIMESTAMPTZ`; connections use UTC. Sensor values use
`NUMERIC(18, 6)` to avoid binary floating-point rounding. Future normalization
must reject unsupported precision/size instead of silently rounding. PostgreSQL
constraints reject negative/NaN values and invalid severities; catalog-dependent
bounds and tag/condition compatibility remain application validation rules.
Warnings are JSON arrays stored alongside accepted events. Rejection errors are
nonempty JSON arrays. Completed import counters must satisfy
`records_read = accepted + rejected + duplicates`, with warning counts no greater
than accepted counts.

The five business tables are accompanied by Alembic's `alembic_version` table.
The catalog seed inserts missing entries without overwriting existing data;
future catalog changes require explicit versioned updates.

### Connection Configuration

Inside Compose, the database hostname is `db`. `ALARM_DATABASE_URL` must match the
`POSTGRES_*` settings; credentials with special characters must be URL-encoded.
The connection string is excluded from settings representations using `SecretStr`.
A local host process needs a reachable PostgreSQL instance and a URL containing
`localhost`; the Compose database port remains private by default.

### PostgreSQL Integration Tests

The tests require `ALARM_TEST_DATABASE_URL`. Without it, database integration tests
are skipped; an offline migration SQL test still runs. Integration tests create
and remove a unique temporary schema, leaving the business tables untouched. Run
against a development/test database with permission to create schemas.

To run all tests inside a temporary API container, from PowerShell:

```powershell
docker compose run --rm -v "${PWD}/tests:/app/tests:ro" -e ALARM_TEST_DATABASE_URL=postgresql+psycopg://alarm_user:local_dev_password@db:5432/alarms api sh -c "python -m pip install --user pytest httpx && python -m pytest /app/tests -p no:cacheprovider"
```

If credentials were customized, replace the test URL accordingly. This installs
test tools only in the temporary container. Checks cover migration reversal,
model/schema agreement, source-event uniqueness, foreign keys, UTC timestamps,
import counter constraints, rejection structure, and repeat catalog loading.

## Project Structure

- `src/alarm_service/domain`: business entities and rules.
- `src/alarm_service/application`: use cases, ports, and normalization.
- `src/alarm_service/infrastructure`: database and file adapters.
- `src/alarm_service/api`: HTTP routes and request/response schemas.
- `scripts`: synthetic dataset generation.
- `datasets/raw`: representative source files.
- `tests/unit`: domain and normalization tests.
- `tests/integration`: database and API tests.
- `docs`: architecture and API usage documentation.

## Postman Endpoint Checks

Import the collection and local environment from `docs/postman`, then select
**Industrial Alarm Service - Local**. Its `base_url` defaults to
`http://127.0.0.1:8000`. Start Docker and import the dataset before execution.

Use **Run collection** to execute 10 read-only requests with 20 concise tests:

1. Service status.
2. Paginated alarm listing.
3. Time filter.
4. Severity filter.
5. Tag filter.
6. Combined filters.
7. Top tags.
8. Top tags with time and severity filters.
9. Invalid time range (422).
10. Invalid page number (422).

Tests check HTTP status, response structure, pagination, alarm filter semantics,
and ranking limits. The pytest suite covers the remaining edge cases and exact
aggregation results. Capture the actual Postman Runner summary as submission
evidence; a collection file alone does not demonstrate a Postman execution.
