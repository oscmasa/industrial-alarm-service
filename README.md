# Industrial Alarm Service

A Python service for importing, cleaning, normalizing, and querying
historical industrial alarm data through an API.

## Context

The dataset represents a fictional water treatment and bottling plant
with one production line and seven equipment units monitored by a
single SCADA system.

Each record represents an alarm activation.
The data is synthetic and intentionally includes data quality issues.

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

Database migrations and alarm queries are not implemented yet.

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
