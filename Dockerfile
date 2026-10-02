FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY alembic.ini ./
COPY migrations/ ./migrations/
RUN python -m pip install . \
    && useradd --create-home --uid 10001 appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "alarm_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
