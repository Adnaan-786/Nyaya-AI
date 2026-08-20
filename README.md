# NyayaAI Server

## Build status (per Part 1 plan, Section C)

| Module | Status |
|--------|--------|
| M1 — Foundations | Done |
| M2 — Database Schema & Tenancy | Done |
| M3 — Auth, RBAC, Devices | Done |
| M4 — Core CRUD | Done |
| M5 — eCourts Sync Service | Done |
| M6 — Document Pipeline | Done |
| M7 — AI Services | Partial (this update — research not started) |
| M9 — Notifications | Not started |
| M10 — Billing and Payments | Not started |
| M11 — Audit, DPDP, Retention | Not started |
| M12 — Hardening and Deployment | Not started |

## 🚀 Module Highlights

### M7 highlights (partial — summarizer only)

M7 is the largest module in the plan (four job types: summarize,
research, draft, risk_review) and is built incrementally.
**Summarize, risk_review, and draft are done end-to-end; research
(RAG over Indian Kanoon) is the one remaining job type.**

- **Async job framework** (contract B.7, plan C.9): `app/services/ai_job_service.py`
  implements the shared `queued → running → done|failed` lifecycle
  every AI job type uses — job creation, a per-tenant **concurrency
  cap** (in-flight `queued`+`running` jobs) and a **daily quota**,
  both raising `402 QUOTA_EXCEEDED` with `details.limit`/`details.plan`
  exactly as the contract specifies. Per-plan overrides are a
  placeholder default until M10's billing plans table exists —
  flagged explicitly in code, not silently assumed.
- **Status wording**: the DB enum (from M2) uses
  `pending/running/completed/failed` internally; the API always
  returns the contract's exact wording `queued/running/done/failed`
  via `ai_job_service.wire_status()` — same "map at the boundary,
  don't rename the enum" policy as M4/M5's known deviations.
- **Worker** (`app/workers/ai_worker.py`): one Celery task dispatches
  by job type via a handler registry (`_HANDLERS`) — adding research
  later is purely additive, no framework changes needed. Enforces the
  per-type timeout from plan C.9 (`asyncio.wait_for`), marks the job
  `failed` with a clear error on timeout or exception (no silent
  retries that could double AI spend), and sends an in-app
  `ai_job_complete` notification on success (reusing M5's
  `notification_service`).
- **LLM provider** (`app/integrations/llm.py`): same FAKE_MODE
  philosophy as every other integration — the real Anthropic Messages
  API call is implemented (not a stub!) behind
  `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, but defaults to a
  **deterministic, heuristic-based fake completion**
  (`app/ai/fake_llm.py`, keyed off a `TASK:` tag every prompt's system
  message starts with) so the entire pipeline is exercisable and
  testable completely offline. The fake responses are regex/keyword
  heuristics over the real input text (not canned strings), so they
  genuinely exercise the same JSON-parsing/markdown-rendering code
  real responses would also go through.

**Summarizer** (`app/ai/summarizer.py`) — `POST /ai/summarize`:
doc-type detection (chargesheet/judgment/notice/agreement/other) via a
cheap classification prompt, then a type-focused extraction prompt.
Long documents (>1200 words) run **map-reduce over the chunks M6
already produced** — per-chunk extraction, then a reduce pass that
deduplicates sections/dates/parties and asks the model to combine the
partial summaries into one coherent one. Output always matches the
contract's exact B.7 shape. Mirrors the user's `language`.

**Risk review** (`app/ai/risk_review.py`) — `POST /ai/risk-review`:
segments contract text into clauses (prefers numbered-clause
boundaries standard in Indian legal drafting, falls back to paragraph
breaks), then runs a per-clause risk prompt returning
severity/explanation/suggestion, matching contract B.7's shape exactly.

**Draftsman** (`app/ai/templates.py`, `app/services/draft_service.py`,
`app/ai/docx_generator.py`) — `GET /ai/templates`, `POST /ai/draft`:
- **13 templates** with typed field schemas (bail application, §138 NI
  Act notice, rent agreement, vakalatnama, plaint, written statement,
  RTI application, consumer complaint, affidavit, reply to legal
  notice, maintenance petition, anticipatory bail, adjournment
  application). *Deviation from plan wording:* the plan's "12 launch
  templates" bullet list groups "plaint/written statement skeletons"
  as one item; they're kept as two separate templates here since
  they're genuinely different documents filed by different parties at
  different stages of a suit — same "flag the deviation" policy as
  M4's CaseStatus wording note.
- Optional `case_id` **auto-fills common fields from real case data**
  (court name, case number) when the caller didn't already supply
  them — drawing on data already in the tenant's own database, never
  inventing anything.
- Required fields the caller didn't supply are reported in
  `missing_fields[]` rather than the model inventing placeholder facts
  (contract B.7: "Unfilled required fields -> missing_fields[], never
  invented facts") — verified with a test that partial input still
  produces a best-effort draft plus an accurate missing-fields list.
- Generated markdown is converted to a real DOCX
  (`app/ai/docx_generator.py`, using `python-docx`) and uploaded to
  S3/MinIO, returning a presigned `docx_url` — verified end-to-end in
  fake mode (valid DOCX zip signature, readable paragraph text).
  
**Not yet built in M7:**
- **Researcher** (RAG over Indian Kanoon), **Draftsman** (12 launch
  templates + DOCX generation), and **Risk review** — all three need
  their own design pass (Indian Kanoon API integration + citation
  verification for research; python-docx templates for draftsman).
  The job framework above is ready for them; each is "write a handler
  function + a route," not new infrastructure.
- The 50-item lawyer-reviewed **golden-set eval suite** (plan C.9)
  can't be built without real reviewed data — this needs your input,
  not credentials, so it's a genuinely different kind of blocker than
  NAPIX/Document AI/OpenAI.
- Per-tenant AI cost/token logging and dashboarding (plan C.9: "Log
  token costs per job") — straightforward to add once real LLM calls
  are live and there's an actual cost to track.


### M6 highlights

- **Presigned upload flow** (contract B.9): `POST /documents/upload-url`
  validates size (≤50MB) and mime type against the contract's allowed
  list, creates the `Document` row, and returns a 15-min presigned S3
  PUT URL keyed `tenants/{tenant_id}/documents/{document_id}/{name}`
  (`app/integrations/storage.py`, boto3 against MinIO locally / real
  S3 in staging-prod — same client code, only the endpoint URL
  changes). `POST /documents/{id}/confirm` enqueues the processing
  pipeline; `GET /documents/{id}` issues a fresh 15-min presigned GET
  and writes an audit-log row for every download, per contract.
- **Processing pipeline** (`app/workers/document_worker.py`, plan
  C.8.2): OCR → chunk → embed → `ocr_status=done`, run as a Celery
  task. DOCX gets plain text extraction (no OCR needed); PDFs/images
  go through Document AI first with an automatic Tesseract fallback.
  Failures are caught, logged to Sentry, and retried up to 3 times
  with exponential backoff; `ocr_status` flips to `failed` with the
  error message stored on the document.
- **OCR provider abstraction** (`app/integrations/ocr/`): Document AI
  is left `NotImplementedError` (no GCP credentials yet — same
  no-guessing policy as NAPIX/commercial-eCourts), but **Tesseract is
  fully implemented and real** since it's an open-source binary, not a
  paid/keyed API — genuinely different from the other stubbed
  integrations. `FAKE_MODE=true` (the default) skips all of this for
  fully offline dev/CI.
- **Chunking & embeddings**: ~600-word chunks with overlap
  (`app/services/chunking.py`, standing in for "~800 tokens" without
  pulling in a tokenizer dependency) → embedded via
  `app/integrations/embeddings.py`. The embedding provider is also
  intentionally stubbed (no OpenAI key), but `FAKE_MODE` produces
  deterministic hash-based vectors so the full chunk→embed→pgvector
  round-trip is testable offline — same philosophy as everywhere else.
- **Universal search** (`GET /search?q=&type=`,
  `app/services/search_service.py`): genuinely hybrid retrieval —
  Postgres full-text search over `ocr_text` (GIN index), trigram
  fuzzy matching on document/case/client names (`pg_trgm`), and
  pgvector cosine-similarity over chunk embeddings (HNSW index) —
  merged with reciprocal rank fusion. Strictly tenant-scoped, with
  highlighted snippets via `ts_headline`.
- **Migrations**: the search-indexes migration
  (`aa7202907aac_add_search_indexes.py`) enables `pg_trgm`, adds GIN
  indexes on `ocr_text`/name columns, and an HNSW index on
  `doc_chunks.embedding`.
- Added `tesseract-ocr` + `poppler-utils` to the Dockerfile (Tesseract
  and `pdf2image` need the system binaries, not just the Python
  packages) and regenerated `uv.lock` to match `pyproject.toml`
  (boto3, pytesseract, pillow, pdf2image, python-docx, celery, httpx).
- `GET /cases/{id}/timeline` now includes document-upload events
  alongside hearings and notes, closing the gap flagged in M4's README
  ("document/status-change events are added once M6/M11 land").
  Status-change events remain an M11 item.

**Not yet built in M6:** the real Google Document AI HTTP integration
(blocked on GCP credentials, same reasoning as NAPIX/commercial
eCourts), and the real OpenAI (or other) embedding provider call. Both
have a single, clearly-marked `NotImplementedError` to fill in once
credentials exist; nothing else in the pipeline needs to change.

### M5 highlights

- **Provider abstraction** (`app/integrations/ecourts/`): `ECourtsProvider`
  interface with `lookup_cnr`, `case_status`, `cause_list`. Three
  implementations — `FixtureProvider` (recorded data, default, fully
  offline), `NapixProvider` and `CommercialProvider` (both real HTTP
  integration points, correctly left `NotImplementedError` until API
  keys are provisioned, same pattern as MSG91 in M3). Swapping
  providers is one env var: `ECOURTS_PROVIDER=fixture|napix|commercial`.
- **Fixtures**: `app/fixtures/ecourts_fixtures.json` ships 25 seeded
  CNRs, 3 of which are "mutable" — calling
  `trigger_fixture_mutation()` flips them to a changed state (new
  stage, next hearing date, an extra history entry) so the diff
  detection + notification pipeline can be exercised deterministically,
  exactly as needed for the plan's IC-1 checkpoint.
- **Routes**: `POST /cases/lookup-cnr` (24h-cached preview, 503
  `UPSTREAM_UNAVAILABLE` on provider failure), `POST /cases/from-cnr`
  (creates a case, stores `raw_ecourts`, marks `ecourts_synced=true`),
  `POST /cases/{id}/sync` (manual force-refresh, rate-limited
  1/hour/case).
- **Diff detection + notify**: `app/services/ecourts_service.py`
  compares `stage`, `next_hearing_date`, and history length against
  the case's last known state; on any change it writes an in-app
  `case_update` notification (`app/services/notification_service.py`)
  for every assigned user. Full FCM/WhatsApp/SMS delivery is M9's
  dispatcher — the in-app row is ready for it to wrap.
- **Scheduled polling** (`app/workers/`): a Celery app + beat schedule
  matching the plan exactly — daily 06:00 IST baseline for every
  synced case, plus 14:00 and 19:00 IST re-checks for cases with a
  hearing today. Paced with a token bucket
  (`app/core/rate_limiter.py`) to respect (and control the cost of)
  commercial-provider rate limits; consecutive provider failures per
  case are counted (`Case.sync_failure_count`) and logged as a warning
  once they hit the configured threshold, ready for M12's alerting to
  pick up. `docker-compose.yml` now has `worker` and `beat` services.
- CNR format validation (16-char alphanumeric, module M4) is reused
  here rather than duplicated.

**Not yet built in M5:** the real NAPIX/commercial HTTP response
normalization (blocked on API approval/vendor docs per plan C.1 — the
`NotImplementedError` is intentional, not an oversight), and the
`GET /cases` `next_hearing_before` filter mentioned in the endpoint
- catalog (straightforward addition to `case_service.list_cases` when
prioritized).
Real NAPIX/commercial provider HTTP calls raise NotImplementedError — This is intentional, not incomplete work. Your plan itself says NAPIX approval "can take weeks" and to use the commercial API as fallback until then. I don't have real API credentials or response schemas for either, so writing fake HTTP parsing code now would just be guessing at a shape I'd have to rewrite anyway. The FixtureProvider is fully functional and is literally what your plan says staging should run on. The moment you get NAPIX/Surepass credentials and can show me a sample response, filling in those two files is small.
next_hearing_before query filter missing — Contract B.6 mentions GET /cases?...&next_hearing_before= as a filter option. I built status, court, assigned_to, and q filters but skipped this one. Genuinely just an oversight/lower priority, not a dependency issue — trivial to add.


### M4 highlights

- **Clients**: `GET/POST /clients`, `GET/PATCH/DELETE /clients/{id}`,
  `POST /clients/{id}/invite` (provisions a `role=client` login via the
  same OTP flow), `GET /clients/{id}/cases`.
- **Cases**: `GET/POST /cases` (manual creation only — CNR/eCourts
  lookup is module M5), `GET/PATCH/DELETE /cases/{id}` (soft delete →
  `status=archived`), `POST /cases/{id}/hearings`,
  `GET /cases/{id}/hearings`, `PATCH /hearings/{id}`,
  `POST /cases/{id}/notes`, `GET /cases/{id}/timeline` (merged,
  descending read model of hearings + notes — document/status-change
  events are added once M6/M11 land).
- **Tasks**: `GET/POST /tasks`, `PATCH /tasks/{id}`.
- **Time & billing capture**: `GET/POST /time-entries`,
  `GET/POST /expenses` (invoice/payment endpoints remain M10).
- **Calendar**: `GET /calendar?from=&to=`, `GET /calendar/today` —
  hearings grouped by date; `firm_admin` sees the whole firm's
  calendar, other roles see only hearings for cases they're assigned to.
- **Firm/team**: `GET/PATCH /firm`, `GET /firm/members`,
  `POST /firm/members/invite`, `PATCH/DELETE /firm/members/{id}`.
- CNR format validation (`app/services/case_service.py::validate_cnr`)
  is ready for module M5 to reuse.
- Every mutating route runs through the RBAC `require()` dependency
  from M3; see `app/core/rbac.py` for the updated capability matrix
  (added `tasks.read`/`tasks.write`).

**Known deviation from the contract prose:** `Case.status` uses
`open|closed|archived` (as already defined in `app/db/enums.py` during
M2) rather than the contract's `active|disposed|archived` wording. The
values are consistent everywhere in code today; reconciling the exact
wording with the Android team's contract is a one-line enum + migration
change whenever that's prioritized.

**Not yet built in M4:** the full client-portal `/portal/*` routes
(scoped case/invoice views for `role=client`) — those are called out
separately in contract B.6 and fit better alongside M10 (billing),
since `/portal/invoices` needs the invoice model. The invite flow above
already provisions the login account so portal routes can be added
without further auth changes.
- Client-portal /portal/* routes not built — The contract lists GET /portal/cases, GET /portal/cases/{id}, GET /portal/invoices as a separate section (B.6 "Client mode"). I built the invite flow (so a client can already log in and get role=client), but the portal endpoints themselves — especially /portal/invoices — need the Invoice model, which doesn't exist until M10 (Billing). Building /portal/cases alone now would mean building it twice (once now, once properly wired to invoices later), so I deferred the whole portal surface to land together with M10.
Case.status wording mismatch — Your contract prose says active|disposed|archived. The actual enum baked into the database back in M2 uses open|closed|archived. This was already decided before I started M4 — I didn't introduce it, I just flagged it since it's a real, if minor, divergence from your Android contract's exact wording. It's cosmetic (a one-line enum rename + migration) but worth you knowing about since the Android team will see whatever the OpenAPI spec says.


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


### M1 - Foundations (Week 1)
- FastAPI skeleton with `/v1/health` endpoint.
- Envelope middleware: all responses wrapped in `{success, data, meta}`; errors mapped to contract codes.
- Structured JSON logging with request IDs (propagated into Celery tasks).
- Environment-driven settings (12-factor); all env vars documented.
- Authoritative `openapi.yaml` created from contract; CI validates generated spec against it.




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
`tests/test_rbac.py` and `tests/test_case_cnr.py` are pure unit tests and need no infrastructure.

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

