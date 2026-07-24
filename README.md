# NyayaAI Server

## Requirements

- Python 3.12+
- Docker
- uv

## Local Development

uv venv
uv sync
uv run uvicorn app.main:app --reload

## Docker

docker compose up --build

## Tests

pytest

## Lint

uv run ruff check .

## API Docs

/docs
/openapi.json

## Environment Variables

| Variable | Description | Required |
|-----------|-------------|----------|
| SECRET_KEY | JWT signing key | Yes |
| DATABASE_URL | PostgreSQL connection | Yes |
| REDIS_URL | Redis connection | Yes |
| MINIO_ENDPOINT | MinIO endpoint | Yes |
| MINIO_ACCESS_KEY | MinIO access key | Yes |
| MINIO_SECRET_KEY | MinIO secret | Yes |
| MINIO_BUCKET | Storage bucket | Yes |
| LOG_LEVEL | Logging level | No |
| SENTRY_DSN | Sentry DSN | No |
| OCR_PROVIDER | OCR provider | No |
| LLM_PROVIDER | LLM provider | No |
| FAKE_MODE | Enable mock integrations | No |