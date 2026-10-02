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
The dataset contract, industrial catalog, and reproducible CSV generator are implemented. Ingestion is pending.

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

Database models and the initial migration are implemented. Alarm ingestion and queries are pending.

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
