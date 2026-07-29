# NyayaAI Server

## Build status (per Part 1 plan, Section C)

| Module | Status |
|--------|--------|
| M1 — Foundations | Done |
| M2 — Database Schema & Tenancy | Done |
| M3 — Auth, RBAC, Devices | Done (this update) |
| M4 — Core CRUD | Not started |
| M5 — eCourts Sync Service | Not started |
| M6 — Document Pipeline | Not started |
| M7 — AI Services | Not started |
| M9 — Notifications | Not started |
| M10 — Billing and Payments | Not started |
| M11 — Audit, DPDP, Retention | Not started |
| M12 — Hardening and Deployment | Not started |

## 🚀 Module Highlights

### M1 - Foundations (Week 1)
- FastAPI skeleton with `/v1/health` endpoint.
- Envelope middleware: all responses wrapped in `{success, data, meta}`; errors mapped to contract codes.
- Structured JSON logging with request IDs (propagated into Celery tasks).
- Environment-driven settings (12-factor); all env vars documented.
- Authoritative `openapi.yaml` created from contract; CI validates generated spec against it.


### M2 - Database Schema & Tenancy (Week 1-2)
- Every business table carries `tenant_id` (UUID NOT NULL).
- Isolation enforced at:
  - Application layer: queries require tenant context from JWT.
  - Database layer: PostgreSQL Row-Level Security (RLS) policies.
- Core tables: tenants, users, clients, cases, hearings, documents, doc_chunks (with embeddings), ai_jobs, invoices, payments, tasks, notifications, devices, audit logs, consents, otp_requests.
- Indexes: optimized for hearings, cases, documents, embeddings (GIN/HNSW).
- All tenant tables have RLS enabled.
- FORCE ROW LEVEL SECURITY is enabled.
- Tests must be run using a non-superuser   application role.
- Using postgres (superuser/BYPASSRLS) will bypass tenant isolation and cause the RLS test to fail.



### M3 highlights

- `POST /auth/otp/request`, `POST /auth/otp/verify` — OTP login with
  5-minute expiry and a 3-requests/hour rate limit per phone
  (`app/services/auth_service.py`, `app/models/otp_request.py`).
- `POST /auth/refresh` — refresh-token rotation with reuse detection:
  replaying an already-used refresh token revokes the whole token
  family (`app/models/refresh_token.py`).
- `POST /auth/onboard` — fills in the profile/role/firm name for a
  brand-new user created during OTP verify.
- `GET/PATCH /me`, `POST/DELETE /devices` — profile + FCM device
  registration.
- `app/core/rbac.py` — the RBAC capability matrix, coded as data, plus
  a `require("capability")` FastAPI dependency. `GET /firm` is wired up
  as a firm_admin-only example.
- Fixed a pre-existing bug: the initial Alembic migration's `upgrade()`
  was a no-op and never created any tables. It now delegates to
  `Base.metadata.create_all(...)`, so all ORM models (including new
  ones from later modules) are created consistently.

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

Note: `tests/test_rls.py` and `tests/test_repository.py` need a live
Postgres (see docker-compose.yml). `tests/test_security.py` and
`tests/test_rbac.py` are pure unit tests and need no infrastructure.

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
| ACCESS_TOKEN_EXPIRE_MINUTES | JWT access-token lifetime | No (default 30) |
| REFRESH_TOKEN_EXPIRE_DAYS | Refresh-token lifetime | No (default 30) |
| OTP_LENGTH | OTP digit length | No (default 6) |
| OTP_EXPIRE_MINUTES | OTP validity window | No (default 5) |
| OTP_MAX_PER_HOUR | OTP send rate limit per phone | No (default 3) |
| OTP_MAX_VERIFY_ATTEMPTS | OTP verify attempt limit | No (default 5) |
| LOG_LEVEL | Logging level | No |
| SENTRY_DSN | Sentry DSN | No |
| OCR_PROVIDER | OCR provider | No |
| LLM_PROVIDER | LLM provider | No |
| FAKE_MODE | Enable mock integrations | No |

