# nyayaai-server

Part 1: the REST API, database and AI pipelines behind the NyayaAI Android app.

## Run it

```bash
cd server
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Postgres is expected on `/tmp` port 5433 (see `app/core/config.py`); override with
`DATABASE_URL`. Interactive docs at `/docs`, and the generated contract at
`/openapi.json`.

## Migrations

The schema is owned by Alembic (`migrations/`). Startup calls `ensure_schema()`, which
brings any database to head unattended, so a fresh clone needs no migration step — just
run it.

To change the schema, edit the models and generate a migration:

```bash
./.venv/bin/python -m alembic revision --autogenerate -m "what changed"
```

Then **read the generated file before committing it.** Autogenerate is a good first
draft, not an authority: it cannot see a column rename (it emits a drop plus an add,
which silently discards the data), and it does not know which changes need a backfill or
will lock a large table. Format it with `ruff format migrations/` — there is deliberately
no post-write hook, because one that resolves `ruff` from `PATH` fails on a fresh
checkout where ruff lives in `.venv/bin`.

Useful checks:

```bash
./.venv/bin/python -m alembic check              # models vs database: any drift?
./.venv/bin/python -m alembic upgrade head --sql # print the SQL instead of running it
```

`alembic check` is the one worth running before you push — it fails when the models and
the migrations have drifted apart, which is the failure this whole directory exists to
prevent.

### The baseline, and why the deployed database is stamped

`ensure_schema()` handles three cases. An empty database gets every migration. A database
already under Alembic gets the normal upgrade. And a database that has this app's tables
but no `alembic_version` — which is exactly what was deployed before this landed, built
by the old `create_all()` plus hand-written `ALTER`s — is **stamped** at the baseline
revision rather than migrated, because running `CREATE TABLE` against it would fail.

The baseline was verified by diffing `pg_dump --schema-only` of a database built the old
way against one built by the migration: identical but for the ordinal position of
`users.is_active`, which sits last in the deployed database because it arrived through
`ADD COLUMN`. Postgres cannot reorder columns and SQLAlchemy always names them
explicitly, so that difference is cosmetic and permanent.

## The contract

Now that both halves of the product are ours, **the OpenAPI document FastAPI generates
from these Pydantic schemas is the integration contract.** There is no hand-authored
YAML to drift from, and the client regenerates against `/openapi.json`.

Two conventions the Android client depends on, enforced here:

- **Money is integer paise.** `BigInteger`, never numeric or float.
- **Calendar dates are `date`, not `datetime`.** `hearings.date`,
  `cases.next_hearing_date` and `invoices.due_date` are days on a cause list. Storing
  or serialising them as instants is what shows a lawyer the wrong hearing day in any
  timezone behind UTC.

## FAKE_MODE

Every third-party integration honours `FAKE_MODE` (default on). This is not only for
offline development — it is what keeps the product demonstrable while the India-specific
approvals are still in flight:

| Integration | Real path | Fake path |
|---|---|---|
| MSG91 SMS | needs a DLT-registered template | OTP is always `123456`, logged |
| eCourts | NAPIX approval or a commercial provider | deterministic synthetic case data from the CNR |
| Razorpay | live keys after KYC | orders marked paid on verify |
| LLM | Anthropic API | canned responses |

Flip individual integrations on by setting their keys and `FAKE_MODE=false`.

## Envelope

Every `/v1` response uses `{success, data, error, meta}` (B.3), including errors —
enforced centrally in `app/core/envelope.py` so an unhandled exception or an unknown
route cannot return a bare FastAPI `{"detail": ...}` and crash the client.
