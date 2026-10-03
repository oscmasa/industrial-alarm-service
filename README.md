# Industrial Alarm Service

A Python service that cleans and normalizes legacy industrial alarm CSV exports,
stores accepted events in PostgreSQL, and exposes alarm queries and metrics through FastAPI.
Rejected records and import executions are retained for traceability.

## Industrial Context and Dataset

The fictional AquaLine water treatment and bottling plant has one production line,
seven equipment units, twelve tags, and one SCADA source (`SCADA_01`). Tanks, a pump,
filtration equipment, a filler, a conveyor, and an air compressor belong to the same
production process. One CSV row represents an alarm activation, not a periodic measurement.
Acknowledgements, clearances, and alarm durations are outside the scope.

The committed sample covers September 2026, with synthetic operating hours of
06:00-22:00 in `America/Bogota`. Thresholds, priorities, temporal patterns, and error
rates are exercise assumptions, not observed plant statistics. UTC conversion can
place late September 30 events on October 1.

The CSV fields are `event_id`, `occurred_at`, `tag`, `alarm_code`, `severity`,
`message`, and `value`. Only message and value are optional. Equipment and units
come from the catalog rather than being repeated in every event.

| Generation category | Rows | Purpose |
| --- | ---: | --- |
| Canonical valid | 8,500 | Baseline events, including valid events with warnings |
| Recoverable | 1,000 | Whitespace, aliases, heterogeneous dates/decimals, optional nulls |
| Invalid | 300 | Missing required fields, invalid dates, identifiers, types or ranges |
| Exact duplicates | 200 | Verify deduplication and repeat-import behavior |

See the [dataset contract](datasets/README.md) for the equipment catalog, field types,
accepted formats, rejection rules, generation parameters, and process diagram.
The accompanying manifest describes generator expectations; the importer never
uses it to decide whether a row is valid.

## Quick Start with Docker

Requirements: Git and Docker Desktop running in Linux container mode, with Docker
Compose available. The commands below use PowerShell from the project root.
Local Python and an `.env` file are not required for this path.

```powershell
git clone https://github.com/oscmasa/industrial-alarm-service.git
cd industrial-alarm-service
docker compose up --build -d --wait
docker compose exec api python -m alembic upgrade head
docker compose exec api python -m alarm_service.infrastructure.database.seed
docker compose run --rm -v "${PWD}/datasets/raw:/data:ro" api python -m alarm_service.cli --input /data/alarms.csv --batch-size 1000
```

If the repository is private, cloning requires an account with access. If you
already cloned it, start with the Docker command. Stop any local server using
port 8000 first. Migrations, catalog loading, and imports are explicit operations;
starting the API alone does not create tables or load events.

On a fresh database, the default CSV import reports:

```json
{
  "status": "COMPLETED",
  "records_read": 10000,
  "accepted": 9500,
  "rejected": 300,
  "duplicates": 200,
  "accepted_with_warnings": 167
}
```

The actual response also includes a generated import ID, source system, and file
SHA-256. Repeat the import command to verify idempotency: accepted becomes 0,
rejected stays 300, duplicates becomes 9,700, and accepted_with_warnings becomes 0.
The alarm count remains 9,500; each execution retains its own audit and rejection records.
Migrations and catalog seeding can also be rerun without duplicating catalog entries.

- Frontend: http://127.0.0.1:8080 (paginated alarm history)
- Interactive API documentation: http://127.0.0.1:8000/docs
- Alarm listing: http://127.0.0.1:8000/api/alarms?page=1&page_size=10
- Top tags: http://127.0.0.1:8000/api/metrics/top-tags?limit=5
- Service status: http://127.0.0.1:8000/status

`GET /status` returns `{"status":"ok"}` and checks HTTP liveness only; it does not
verify database connectivity or schema readiness.

```powershell
docker compose ps
docker compose logs frontend api db
docker compose down
```

Stopping the services preserves the `postgres_data` volume. `docker compose down -v`
deletes that database volume; use it only for an intentional local reset.

## API Queries

### Alarm Listing

`GET /api/alarms` returns accepted events ordered by occurrence time descending,
then internal ID descending. Optional filters combine with AND.

| Parameter | Contract |
| --- | --- |
| start_time | Inclusive ISO 8601 timestamp with Z or an explicit UTC offset |
| end_time | Exclusive ISO 8601 timestamp with Z or an explicit UTC offset |
| severity | LOW, MEDIUM, HIGH, or CRITICAL |
| tag | Exact identifier, trimmed and normalized to uppercase |
| page | 1-100,000; default 1 |
| page_size | 1-100; default 50 |

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/alarms?severity=HIGH&tag=PUMP_01_FLOW&page_size=10"
Invoke-RestMethod "http://127.0.0.1:8000/api/alarms?start_time=2026-09-15T05:00:00Z&end_time=2026-09-16T05:00:00Z"
```

The second example selects September 15 in the plant's UTC-05 timezone. Encode
positive-offset plus signs as `%2B` when constructing URLs manually.

Responses contain `items` and `pagination` (`page`, `page_size`, `total`,
`total_pages`). Events include their source/import references, UTC timestamp,
tag, alarm code, severity, message, value, and warning codes. Decimal values are
JSON strings to preserve precision; missing optional values are JSON nulls.
No matches return HTTP 200 with an empty list. A valid unknown tag also returns
no matches. A page beyond the final page retains the matching total.

### Top Tags

`GET /api/metrics/top-tags` accepts `start_time`, `end_time`, and `severity` with
the same semantics. `limit` accepts 1-100 and defaults to 10.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/metrics/top-tags?severity=HIGH&limit=5"
```

The response contains `items` with `tag` and `event_count`, plus `limit`. Ranking
uses count descending, then tag ascending for ties. Counts include accepted
warnings, exclude rejected records, and are not inflated by duplicate imports.
They combine sources within the fixed plant catalog. An event count does not
represent alarm duration or establish a root cause.

### Validation and Errors

Invalid ranges (`start_time >= end_time`), timestamps without offsets, unsupported
query parameters, invalid severity, and out-of-range pagination/limits return
HTTP 422 with structured validation errors. Database-operation failures return
a generic HTTP 503 without exposing SQL, credentials, or tracebacks.

## Cleaning and Import Decisions

The CSV adapter streams records through a shared normalizer. Python's standard
library handles CSV, explicit datetime parsing, and `Decimal` conversion;
Pydantic validates the normalized structure. Pandas is unnecessary for row-level
rules and would add a dependency without improving this bounded-memory import.

- Trim fields and recognize explicit null markers; zero remains a valid value.
- Normalize identifiers and map documented severity aliases.
- Interpret supported source dates without offsets in `America/Bogota`; store UTC.
- Accept decimal dots/commas without silently rounding unsupported precision.
- Validate required fields, catalog relationships, message length, and numeric bounds.
- Preserve valid historical severity even when it differs from the catalog default.
- Retain trigger/severity discrepancies as warnings rather than altering historical data.

Acceptance depends on which fields are missing, not the number of missing fields.
Rejected rows preserve original values and structured reasons instead of being
silently deleted. Header/file failures abort the import; readable malformed rows
are rejected individually. The dataset contract lists all rules and error codes.

Imports use bounded batches (default 1,000; allowed 1-5,000), bulk inserts, and one
existing-event lookup per batch. `(source_system, event_id)` identifies an event:
identical normalized events are duplicates; conflicting events are rejected as
`DUPLICATE_CONFLICT`. The first valid occurrence wins and reimports never overwrite it.
The source defaults to `SCADA_01` and can be specified using `--source-system`.

All event/rejection batches share one transaction. Fatal errors roll back those
writes; a separately created import audit is marked `FAILED` while the database
remains reachable. A checksum recheck detects file changes before commit. A
transaction-level advisory lock serializes imports for the same source, with a
30-second lock timeout. Completed imports satisfy:

```text
records_read = accepted + rejected + duplicates
accepted_with_warnings <= accepted
```

Rejected originals containing NUL use a lossless base64 JSON wrapper because
PostgreSQL JSONB cannot store NUL. Other rejected originals retain their field mapping.

## Architecture and Database

The architecture uses domain entities, application use cases and ports, and
infrastructure/HTTP adapters. This keeps business rules independent of FastAPI
and SQLAlchemy without adding a large framework for a small assessment.

| Location | Responsibility |
| --- | --- |
| src/alarm_service/domain | Immutable alarm entities and industrial catalog |
| src/alarm_service/application | Normalization, import/query use cases, and ports |
| src/alarm_service/infrastructure | CSV readers, generators, and SQL adapters |
| src/alarm_service/api | Routes, dependency wiring, and input/output schemas |
| scripts | Dataset generation and normalization preview |
| migrations | Versioned Alembic schema changes |
| tests | Unit and integration coverage |
| docs/postman | API collection and local environment |

PostgreSQL is the relational equivalent chosen for Docker availability, constraints,
transactional imports, and SQL aggregation. SQLAlchemy supplies database access;
Alembic tracks explicit schema evolution. FastAPI provides typed validation and
interactive API documentation.

| Table | Responsibility |
| --- | --- |
| equipment | Physical equipment identifiers and names |
| tags | Signal identifiers, equipment relationships, and units |
| alarms | Accepted events and historical values/warnings |
| imports | File metadata, execution state, timestamps, and counters |
| rejected_records | Original rejected rows and validation errors |

Equipment/tag separation avoids repeating catalog attributes in every event.
Audit tables keep import metadata and rejected rows outside the queried alarm
history. Alembic also maintains its own `alembic_version` table.

Foreign keys restrict deletion of referenced history. A unique constraint enforces
source-event identity. Composite indexes on `(occurred_at, id)`,
`(severity, occurred_at, id)`, and `(tag_id, occurred_at, id)` support common filters
and ordering; their effectiveness should be measured for production workloads.
Timestamps use `TIMESTAMPTZ` and values use `NUMERIC(18, 6)`.

Aggregation runs in SQL rather than loading history into Python. Paginated reads
use one read-only repeatable-read snapshot for both rows and totals. Queries use
bound parameters, a connection pool, and a 10-second statement timeout.

## Local Development and Dataset Generation

Python 3.14 is required. From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/generate_dataset.py --rows 10000 --seed 42
python scripts/check_dataset.py --input datasets/raw/alarms.csv
```

The generator overwrites `datasets/raw/alarms.csv` and its adjacent manifest.
Seed 42 and the default parameters reproduce the sample within the same
Python/timezone-data and generator versions. Generation holds rows in memory;
the importer streams bounded batches.

The preview does not write to PostgreSQL or deduplicate. It reports 9,700 acceptable
rows and 300 rejected rows; deduplication during import reduces accepted events
to 9,500. See the dataset contract for custom periods, rates, and output paths.

To run Uvicorn locally, supply `ALARM_DATABASE_URL` for a reachable PostgreSQL
instance, apply migrations, seed the catalog, then run:

```powershell
python -m alembic upgrade head
python -m alarm_service.infrastructure.database.seed
python -m uvicorn alarm_service.main:app --reload
```

The Compose database is not exposed on a host port, so its `db` hostname works
only inside Compose. Local execution needs its own reachable database or an
explicit host-port configuration.

## Tests and Postman

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest --basetemp=.pytest_tmp -p no:cacheprovider
```

Without `ALARM_TEST_DATABASE_URL`, PostgreSQL integration tests are skipped.
To include them using the running Compose database and default local credentials:

```powershell
docker compose run --rm -v "${PWD}/tests:/app/tests:ro" -e ALARM_TEST_DATABASE_URL=postgresql+psycopg://alarm_user:local_dev_password@db:5432/alarms api sh -c "python -m pip install --user pytest httpx && python -m pytest /app/tests -p no:cacheprovider"
```

If credentials change, update the test URL. Tests create and remove isolated
schemas; the database user must have permission to create schemas. Coverage
includes invalid source data, UTC conversion, precision, duplicate conflicts,
transaction rollback, repeat imports, migrations, pagination, filters, and exact
aggregation results. The previous full PostgreSQL run passed 147 tests. After adding
18 direct use-case checks, the local run passed 149 tests with 16 PostgreSQL tests
skipped; run the Docker command above to verify all 165 tests with a database.

Import these files into Postman:

- `docs/postman/industrial-alarms.postman_collection.json`
- `docs/postman/local.postman_environment.json`

Select **Industrial Alarm Service - Local**, confirm `base_url`, and use
**Run collection** after loading the dataset. The collection contains 10 requests
and 20 checks covering status, listing, individual/combined filters, top tags,
and invalid input (422). The Postman Runner execution passed all 20 checks.

## Frontend Setup

The frontend is an independent React/TypeScript package in `frontend`.
Docker Compose builds the frontend and serves its compiled files through Nginx
at http://127.0.0.1:8080. The dashboard lists real alarms, with 20 events per
page, previous/next navigation, and loading, empty, and retryable error states.
Time, severity, and exact-tag filters are available, together with top-tag metrics. Local Node.js is unnecessary
when using Docker.

Use Node.js 22.12+ within the Node 22 release line, or Node.js 24+.
From the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Stop the development server with Ctrl+C.
For static checks and production compilation:

```powershell
npm run lint
npm test
npm run build
npm run preview
```

The production preview runs at http://127.0.0.1:4173. TypeScript uses strict
checking. `package-lock.json` is committed; `node_modules` and `dist` are generated
and ignored. The client uses browser fetch and AbortController; obsolete page
requests are cancelled and ignored. Tests use the built-in Node.js test runner,
without adding a test framework dependency. Values remain decimal strings, missing
fields are labelled as not recorded, and warning details can be expanded.
Table dates use America/Bogota (UTC-05); hover over a date to see its UTC source.

### Dashboard Filters

Use **Apply filters** to submit an optional start/end time, severity, and exact tag.
Editing a field alone does not change the active query. **Clear filters** resets
both the form and applied filters. Applying or clearing returns to page 1; page
navigation retains the active filters. The applied summary identifies the query
currently used by the table, even while the form is being edited.

Datetime inputs use the plant's UTC-05 clock, explicitly converted to UTC before
sending. The browser's local timezone is not used. This fixed offset matches the
September 2026 scenario; historical daylight-saving periods are outside the UI's
fixed-offset convention. Start is inclusive and end exclusive. An inverted/equal
range, unsupported date, or malformed tag is rejected before requesting data.
Tag values are trimmed and uppercased. Valid unknown tags return no matches.
The API remains the authoritative validator and its 422 errors have a safe UI message.

For a combined example, enter September 15, 2026 at 00:00 as the start and
September 16 at 00:00 as the end, select High, and enter `PUMP_01_FLOW`.
These dates produce a UTC range of September 15 at 05:00 to September 16 at 05:00.
The committed sample contains 39 matching events. No matches show an explicit
empty state; clearing restores the complete alarm history.

### Top-Tag Visualization

The dashboard requests `/api/metrics/top-tags?limit=5` and renders up to five
horizontal bars, with exact event counts and text labels. Ranking and aggregation
come from PostgreSQL through the API, not from the current table page. Bar lengths
are proportional to the largest returned count; ties retain the API's tag order.
The graphic uses HTML/CSS with accessible list labels, without a chart dependency.

Applied time and severity filters update the chart. The tag filter affects only
the alarm list because the metrics endpoint compares tags and does not accept a
tag filter. This distinction is visible above the chart. Page navigation does
not refetch metrics. Chart loading, errors/retry, and empty results are independent
of the table; obsolete requests are cancelled when its filters change.

Counts include accepted events with warnings and exclude rejected/duplicate rows.
They describe activation frequency, not severity scores, duration, or root causes.
`npm test` covers client requests, filter forwarding, cancellation, empty responses,
bar scaling, and failure handling, together with the existing list/filter tests.

### Frontend Container and API Proxy

From the repository root, `docker compose up --build -d --wait` starts the frontend,
API, and database. `FRONTEND_PORT` defaults to 8080 and can be changed in `.env`.
Node builds the application using `npm ci`; the runtime image contains only Nginx
and the compiled files, and runs as an unprivileged user on container port 8080.
The frontend build context is `frontend`, separate from the Python image.

Nginx forwards `/api/` and `/status` to `api:8000`, preserving paths and query
parameters. Browser calls use relative URLs without cross-origin
configuration. Docker DNS is refreshed so API container recreation does not leave
a stale upstream address. Unknown API paths retain the API's error response;
only frontend routes fall back to `index.html`. Fingerprinted assets are cached,
while the HTML entry is revalidated.

After migrations, catalog loading, and import, verify the proxy in PowerShell:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/status"
Invoke-RestMethod "http://127.0.0.1:8080/api/alarms?page=1&page_size=1"
Invoke-RestMethod "http://127.0.0.1:8080/api/metrics/top-tags?limit=1"
```

The frontend health check verifies static HTTP serving; it does not check the
schema or loaded data. API liveness is a startup dependency. In local Vite
execution, Vite proxies /api to http://127.0.0.1:8000; start the API first.
The static production preview does not provide that proxy; use Compose for
an integrated production build. Neither startup nor rebuilding removes the PostgreSQL volume.

## Configuration and Operational Limits

Copy `.env.example` to `.env` only when customizing Compose settings. Settings use
the `ALARM_` prefix; environment variables override `.env`. Changing database
credentials requires matching `ALARM_DATABASE_URL`, and does not change credentials
in an already initialized PostgreSQL volume. URL-encode special characters in passwords.
Set `API_PORT` or `FRONTEND_PORT` to change the corresponding host port, or `ALARM_DOCS_ENABLED=false` to disable
Swagger/OpenAPI. `.env` and generated environment/build files are ignored by Git.

The API binds to host loopback, runs as a non-root container user, and exposes no
database host port. Default credentials are for local development. Authentication,
authorization, TLS, and rate limiting remain necessary before exposing it beyond
this local assessment setup.

CSV is the implemented source adapter; JSON is a possible extension. The plant
catalog is fixed and versioned in code. The frontend implements listing and
pagination, filters, and top-tag visualization. File uploads are outside the current scope.
Offset pagination suits the sample; cursor pagination and
alternative counting strategies are options for larger histories. Imports are
atomic but can create long transactions; resumable checkpoints require an
explicit design. Abrupt termination can leave an audit in `RUNNING`.
Docker provides a repeatable setup, while image tags and dependency ranges are
not an exact dependency lock.
