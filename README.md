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

Initial project structure.

Setup and execution instructions will be added as implementation
progresses.
## Local Development Setup

Python 3.14 is required for the initial project configuration.

From the project root, activate the virtual environment and install the package:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Verify the package installation:

```powershell
python -c "import alarm_service; print('Package imported successfully')"
```

The API, database migrations, and Docker environment are not implemented yet.

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
