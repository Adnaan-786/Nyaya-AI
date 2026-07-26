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
