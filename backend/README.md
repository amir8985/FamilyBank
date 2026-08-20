# FamilyBank API (backend)

FastAPI service implementing `../FamilyBank_architecture.md` sections 2-3:
debt ledger, investing (buy/sell against real Yahoo prices, converted to
the family's home currency), and the scheduler that refreshes
`price_cache` / `fx_rates_cache` together.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # fill in DATABASE_URL, GOOGLE_CLIENT_ID, secrets
alembic upgrade head          # creates tables + seeds the asset catalog
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for the interactive API docs.

## Refreshing prices/FX rates locally

The scheduler is a plain function, not a background process — call its
endpoint whenever you want fresh prices during development:

```bash
curl -X POST http://localhost:8000/internal/refresh \
  -H "X-Scheduler-Secret: $INTERNAL_SCHEDULER_SECRET"
```

In production this is what a Vercel/Railway Cron job hits 4-5x/day
(architecture 5.5) — nothing calls Yahoo per-request or per-family.

## Auth flow

1. Frontend (NextAuth) completes Google sign-in and gets Google's own
   `id_token`.
2. Frontend calls `POST /auth/sync` with that `id_token`. This backend
   verifies it directly against Google (never trusts the frontend's word
   for who the user is), finds-or-creates the family+user, and returns a
   backend-issued session JWT.
3. Every other request carries that JWT as `Authorization: Bearer ...`.
   `family_id` is read out of the JWT server-side — never out of the
   request body/path — so there's no way for one family to address
   another's data (architecture 5.5).

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

Runs against your real `DATABASE_URL` — safe to do, since every test runs
inside one outer transaction that's rolled back at teardown (SQLAlchemy's
`join_transaction_mode="create_savepoint"`, see `tests/conftest.py`), so
nothing a test does is ever visible outside that test or left behind
afterward. Covers:

- `test_fx_service.py` — pure currency-conversion math, no DB
- `test_debts_db_service.py` — the debt ledger (add/deduct/negative/batched balances)
- `test_investing_service.py` — buy/sell atomicity, insufficient-funds,
  overselling, cost averaging, day-change %, catalog ordering, and
  graceful handling of a missing FX rate (regression tests for the real
  bugs found during manual testing: the `func.case()` typo, the enum
  `values_callable` mismatch, and the autobegin/commit issue)
- `test_api_auth.py` — `/auth/sync`, with Google's own verification
  mocked at that one boundary (see its docstring for why)
- `test_api_family_isolation.py` — the property architecture 5.5 flags as
  most important: one family can never reach another's data
- `test_api_e2e_journey.py` — the full parent journey through the real
  API (sign-in → onboarding → kids → debt → buy/sell → settings) — the
  practical equivalent of a browser end-to-end test, since real Google
  login can't be safely scripted (see `../frontend/e2e/` for what *is*
  covered at the browser level)

## Layout

```
app/
  core/       config, db session/transaction helper, JWT + Google verification
  models/     SQLAlchemy models (mirrors architecture.md section 1)
  schemas/    Pydantic request/response models
  services/   debts_db_service, investing_service, fx_service, price_client, catalog_service
  scheduler/  the one global refresh job
  api/        FastAPI routers
alembic/      migrations (0001 schema, 0002 seeds the asset catalog)
```
