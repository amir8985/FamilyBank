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
