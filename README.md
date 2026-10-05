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
Compose available. Use PowerShell; local Python, Node.js and an `.env` file are not
required. Ports 8000 and 8080 must be free unless customized in `.env`.

### Get the Repository

```powershell
git clone https://github.com/oscmasa/industrial-alarm-service.git
cd industrial-alarm-service
```

Private repositories require an account with access. If already cloned, open a
terminal at the project root. Choose **one** of the following setup options; both
prepare the same services, schema, catalog and sample data.

### Option A Automated Setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_project.ps1
```

The script checks Compose and the running Linux Docker engine, builds and starts
all services, applies migrations, seeds the catalog, and imports the committed CSV.
It stops at the first failed command, preserves the database volume and prints the
actual dashboard and API addresses, including custom ports. Docker Desktop must
already be running. The execution policy applies only to this PowerShell process;
it does not change the machine's policy.

Each default run creates a new import execution and its rejection audit; existing
alarms are deduplicated. For an existing database with the desired data, omit the
import:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_project.ps1 -SkipImport
```

`-SkipImport` still starts services, applies migrations and seeds the catalog;
it does not verify that alarms are present. The script resolves project paths from
its own location. It does not generate another CSV or reset the database.

### Option B Manual Setup

Run these steps in order from the project root. If a command fails, resolve its
error before continuing.

**1. Build and start frontend, API and PostgreSQL.**

```powershell
docker compose up --build -d --wait
```

**2. Create or update the database tables.**

```powershell
docker compose exec api python -m alembic upgrade head
```

**3. Load the equipment and tag catalog.**

```powershell
docker compose exec api python -m alarm_service.infrastructure.database.seed
```

**4. Import the committed sample CSV.** No dataset generation is needed to start.

```powershell
docker compose run --rm -v "${PWD}/datasets/raw:/data:ro" api python -m alarm_service.cli --input /data/alarms.csv --batch-size 1000
```

Skip step 4 if the desired events are already loaded. Migrations, catalog loading
and imports are explicit operations: starting the API alone does not create
business tables or load data.

### Verify and Open the Application

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

- Frontend: http://127.0.0.1:8080 (Overview, Alarm history and Data quality)
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

To restart previously initialized services without another import:

```powershell
docker compose up -d --wait
```

If startup fails, use `docker compose ps` and the logs above to identify the
service involved. Docker Desktop must remain running while using the project.
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
Each alarm also exposes `unit` from the persisted tag catalog: `L/min`, `bar`,
`%`, `degC`, or `boolean`. This metadata does not change the captured reading.
The dashboard removes only trailing fractional zeros without converting readings
to JavaScript numbers or rounding them (for example, `6.610000` becomes
`6.61 L/min`). It displays `degC` as `°C`, binary values as `1 — Active` or
`0 — Inactive`, and missing readings as `Not available`. Missing unit metadata
is explicitly marked as `unit not specified`; no unit is inferred from a value.
CSV files, stored readings, and their six-decimal database precision are unchanged.
No matches return HTTP 200 with an empty list. A valid unknown tag also returns
no matches. A page beyond the final page retains the matching total.

### Top Tags

`GET /api/metrics/top-tags` accepts `start_time`, `end_time`, `severity`, `tag`,
and `alarm_code` with
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

### Overview Metrics API

`GET /api/catalog/tags` exposes the fixed configured catalog version, equipment
names, units and compatible `alarm_types` for each tag. The frontend restricts
alarm-type choices after selecting a tag and resets an incompatible selection.
Catalog choices are independent of events available in a selected period;
severity remains independent of each condition's default severity.

Both `/api/metrics/overview` and `/api/metrics/top-tags` accept optional `tag` and
`alarm_code` filters, trimmed and uppercased. Filters combine with time and
severity using AND and apply consistently to all aggregates, trailing averages
and previous-period comparisons. Unknown identifiers or incompatible combinations
return empty metrics; malformed identifiers return 422. Global available event
dates remain independent of these filters.

`GET /api/metrics/available-dates` returns the first and last accepted event
timestamps plus `America/Bogota`. An empty database returns null bounds. These
dates describe observed events, not guaranteed continuous monitoring coverage.

`GET /api/metrics/overview` requires `start_time` and `end_time` with explicit
timezone offsets, at midnight in Bogotá. The start is included and the end is
excluded; ranges are limited to 366 days. Optional `severity` applies to current
counts, the previous period and the moving average alike. For September:

```text
/api/metrics/overview?start_time=2026-09-01T00:00:00-05:00&end_time=2026-10-01T00:00:00-05:00
```

The response includes total events, all four severity counts, daily counts and
a seven-day trailing average including the selected day. The first six days may
use earlier events outside the selected range. An average is null when its
seven-day window extends outside observed event dates. Daily zero counts mean
no stored events, not proof that a machine was operating without alarms.

Comparison uses the immediately preceding interval of equal duration (a 30-day
selection compares against the preceding 30 days, not necessarily a calendar
month). Both intervals must lie within observed event dates. Otherwise the
baseline and percentage are null with `outside_observed_dates`. A zero baseline
returns a null percentage with `zero_baseline`. A nonzero baseline uses
`(current - previous) / previous * 100`. Averages and percentages are JSON decimal
strings rounded to two decimals; captured readings are never rounded or updated.
Date availability does not establish completeness of either period.

All aggregates use accepted unique events, including events with warnings.
PostgreSQL groups by local day and severity within indexed timestamp bounds;
Python processes only the bounded aggregate rows. Counts and date bounds share
a read-only repeatable-read snapshot with a ten-second statement timeout.
The Overview view consumes these endpoints for its month selection, timeline,
summary cards, and filtered tag ranking.

### Data Quality API

`GET /api/imports?page=1&page_size=20` lists audit executions, newest first
(`started_at DESC, id DESC`). Each item includes source, file name, checksum,
status, start/finish timestamps and the five persisted counters. Executions of the
same file remain separate: a repeated load can have zero accepted records and many
duplicates. Accepted-with-warning records are a subset of accepted records, not an
additional outcome. Counters belong to each execution; do not sum repeated imports
as unique events. Pending/running/failed executions may have incomplete counters.
Internal operational exception details are deliberately excluded.

`GET /api/imports/{import_id}/rejections?page=1&page_size=20` returns rejected
records in source-record order, with their original JSON values, issue fields,
codes and messages, and audit timestamp. Optional `error_code=INVALID_VALUE`
filters records containing that exact issue code (trimmed and uppercased).
A record with multiple issues is counted once; all its issues remain in the
response. Unknown valid codes return an empty page. `record_number` is the
one-based CSV data-record number, excluding the header, rather than a guaranteed
physical line number when quoted fields contain newlines. Raw source values remain
unchanged; JSON formatting does not reproduce the original CSV bytes.

Both endpoints return `items` and `pagination` (`page`, `page_size`, `total`,
`total_pages`); rejection responses also identify `import_id`. Page size defaults
to 20 and is capped at 100; pages are limited to 1-100000. Malformed input or
unknown query parameters return 422. An unknown import UUID returns 404, while an
existing import without rejections returns 200 with an empty list. A database
failure returns a safe 503. Read-only repeatable-read transactions keep counts and
items consistent, with a 10-second statement timeout. Existing import-date and
unique `(import_id, record_number)` indexes support ordering and import isolation.
Original records and checksums are audit data; access should be restricted outside
the local demonstration environment.

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
| frontend | React/TypeScript dashboard and Nginx runtime |

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

### Generate Additional Exports Without Identity Conflicts

The generator accepts `--start-id` (default 1) to assign a new event-number range
for another export from the same `SCADA_01` source. For example, after the committed
September sample:

```powershell
python scripts/generate_dataset.py --rows 10000 --seed 99 --start-id 10001 --start 2026-10-01 --end 2026-11-01 --output datasets/raw/alarms_october.csv
docker compose run --rm -v "${PWD}/datasets/raw:/data:ro" api python -m alarm_service.cli --input /data/alarms_october.csv --batch-size 1000
```

The first assigned event is `EVT-00010001`. New manifests (generator version 1.1)
include `start_id`, `end_id`, and `next_start_id`. Use `next_start_id` for the next
file or reserve a larger non-overlapping range. The assigned range includes rows
that are intentionally invalidated; copies reuse their originals' IDs and do not
consume additional numbers. Do not infer the next start from the maximum accepted
ID in the database, because rejected records also used identities.

The start must be an integer from 1 to 99,999,999 and the full assigned range must
fit eight digits. `next_start_id` is null when that range exhausts the format.
The generator does not consult PostgreSQL or allocate ranges automatically: avoid
overlapping ranges when multiple people generate exports. Changing seed or dates
alone does not assign new identities. Reimporting the same file remains idempotent;
reusing an identity with different normalized content remains a conflict.
The committed CSV and its original manifest remain unchanged.
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
aggregation results. Run the full Docker suite to include PostgreSQL checks;
a passing local run with skipped database tests does not validate database behavior.

Import these files into Postman:

- `docs/postman/industrial-alarms.postman_collection.json`
- `docs/postman/local.postman_environment.json`

Select **Industrial Alarm Service - Local**, confirm `base_url`, and use
**Run collection** after loading the dataset. The collection has 19 requests and
38 checks covering status, alarm filters/pagination, top tags, configured catalog,
available dates, two-day comparisons, combined overview filters, import counters,
original rejections, rejection-code filters, 404 and 422 responses. Run in collection
order: Import history sets the collection's `import_id` from a real execution for
subsequent rejection requests. Reimport the updated collection if an earlier
version is already present in Postman. Tests assume the committed September sample
has been loaded. No request writes or reimports data.

## Dashboard and Frontend Development

The frontend is an independent React/TypeScript package in `frontend`.
The shared layout provides **Overview**, **Alarm history**, and **Data quality**
navigation. Switching views preserves the history filters and current page.
Overview uses real available dates to list months and defaults to the latest
observed month. More filters provides an inclusive date range (1-366 days), tag,
compatible alarm types from the configured catalog, and severity. Changing tag
clears an incompatible alarm type. Changing a valid filter automatically updates daily bars, the optional
seven-day moving average, totals, critical events, peak day, and top tags together.
The compact Overview comparison card explicitly names the preceding equal-length
period in days and includes both inclusive date ranges and their event counts.
The percentage describes more/fewer recorded activations, not equipment condition.
Dates include the year and distinguish month/year boundaries. Missing prior data
shows No history, while a zero baseline shows 0 events with an unavailable
percentage; zero is never substituted for missing history.

The applied filter summary remains visible; Clear filters restores the selected
month and all tags, alarm types and severities. Invalid or incomplete dates retain
the previous results until a valid period is selected.
Pagination and filter requests keep the last successful content mounted while
loading; a visible updating notice identifies previous results. Applied summaries
change after successful responses. Pagination is disabled during a request,
obsolete requests are cancelled, and errors retain previous results for retry.
An accessible daily-count table complements the SVG chart. Previous equal-length
period comparisons show missing history explicitly; a zero baseline retains its
zero event count but cannot produce a percentage change. Zero events do not establish monitoring coverage or equipment
health. History filters remain independent. Data quality displays real import executions,
per-execution quality counters and paginated rejected source records.
Docker Compose builds the frontend and serves its compiled files through Nginx
at http://127.0.0.1:8080. The dashboard lists real alarms, with 20 events per
page, previous/next navigation, and loading, empty, and retryable error states.
Local Node.js is unnecessary when using Docker.

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

### History Filter Interaction

History filters are collapsed by default. Expand **Filters** to edit the range,
severity or tag; the applied summary remains visible when collapsed. Table dates
show a full calendar date and a separate 24-hour time in Bogotá (UTC−05:00).
Expand **View message** for the recorded message and the warning count for
normalization warnings. The presentation does not change captured values.

Valid optional start/end times and severity update automatically; exact-tag text
waits 400 ms after the last edit. **Clear filters** resets the fields and query.
Changing or clearing a filter returns to page 1; pagination retains active filters.
The applied summary identifies the successfully loaded query while edits or
requests are pending.

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

Overview top tags use its applied time, severity, tag and alarm-type filters,
independently of history pagination. Chart loading, errors/retry and empty results
are handled explicitly. No illustrative counts are displayed.

Counts include accepted events with warnings and exclude rejected/duplicate rows.
They describe activation frequency, not severity scores, duration, or root causes.
`npm test` covers client requests, filter forwarding, cancellation, empty responses,
bar scaling, and failure handling, together with the existing list/filter tests.

### Data Quality View

The Data quality frontend loads execution options 20 at a time, newest first,
with import-list pagination for older runs. Options include the plant timestamp,
file name, status and short import ID; full ID and checksum are available under
Execution details. Paging the import list preserves the current selection until
a different execution is chosen. The latest execution is selected initially.

Four compact, labelled cards use blue (accepted), red (rejected), purple
(duplicates) and yellow (accepted with warnings). The optional rejection reason code updates automatically after 400 ms of typing; clearing it applies immediately. Invalid codes show an explanation without sending a request. The error-code filter affects
only the rejection table; cards retain the execution totals. Switching executions
clears the issue filter and resets rejection pagination. Each row lists all its
issues, with original JSON in a disclosure. Sticky table headings, bounded table
scroll, explicit empty/error states and retries keep the compact layout usable.
Previous results remain visible with an updating notice during requests; their
execution metadata stays attached until the new results arrive. Obsolete requests
are cancelled. Original JSON is rendered as text, rather than injected HTML.
These endpoints can also be exercised through `/docs`.

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

CSV is the implemented source adapter. The plant catalog is fixed and versioned
in code. The three dashboard views cover overview analytics, alarm history, and
import quality. File uploads and JSON input are outside the implemented scope.
Offset pagination suits the sample; cursor pagination and
alternative counting strategies are options for larger histories. Imports are
atomic but can create long transactions; resumable checkpoints require an
explicit design. Abrupt termination can leave an audit in `RUNNING`.
Docker provides a repeatable setup, while image tags and dependency ranges are
not an exact dependency lock.

## Verification Checklist

Before submitting:

1. Follow Quick Start on a fresh checkout/database: build the containers, apply
   migrations, seed the catalog and import the committed CSV. Use a separate
   Compose project/volume when an existing local database must be preserved.
2. Run the complete PostgreSQL test command under Tests and Postman; a run with
   skipped database tests does not validate persistence behavior.
3. Run backend lint/format checks and the frontend lint, test and build commands.
4. Reimport the updated collection and execute all requests in Postman Runner.
   Import history automatically selects a real import ID for rejection queries.
5. Check all three views: valid and invalid filters, pagination, no matches,
   dependent alarm types, initial/repeated execution counters and original-record
   disclosure. Dates and counts in comparisons must match the selected interval.

Missing previous-period history, no filter matches, unknown import (404), and
invalid input (422) are expected states. Rebuilding containers alone does not
bootstrap the schema or import data; those operations are explicit in Quick Start.
