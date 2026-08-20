# FamilyBank

Parents track allowance/debt owed to their kids; kids "invest" that
virtual balance in real stocks and indices at real market prices — no
real broker, no real money movement. See `FamilyBank_spec.md` and
`FamilyBank_architecture.md` for the full product/architecture spec, and
`design_handoff_familybank/` for the visual design this was built from.

```
backend/    FastAPI service — debt ledger, investing, Yahoo prices + FX, scheduler
frontend/   Next.js 16 app — landing page + the 4 core in-app screens
```

## Running it locally

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env      # see "What you need to provide" below
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local   # see below
npm run dev
```

Visit `http://localhost:3000`.

## What you need to provide

Both are free to obtain and only need to be set once:

1. **A Postgres database** (Supabase or Neon both have workable free
   tiers — per architecture 5.5). Put its connection string in
   `backend/.env` as `DATABASE_URL` (asyncpg driver, e.g.
   `postgresql+asyncpg://user:pass@host:5432/db`).
2. **A Google OAuth client** (Google Cloud Console → APIs & Services →
   Credentials → Create OAuth client ID → Web application). Sign-in is
   Google-only by design — no separate email/password accounts.
   Redirect URI: `http://localhost:3000/api/auth/callback/google`.
   The client ID/secret go in `frontend/.env.local`
   (`AUTH_GOOGLE_ID`/`AUTH_GOOGLE_SECRET`); the same client ID also goes
   in `backend/.env` as `GOOGLE_CLIENT_ID`.

Everything else in `.env.example`/`.env.local.example` is a random
secret you generate yourself (commands are inline in those files) — no
external account needed.

## What's implemented (v1, per the spec)

- Google-only auth; first sign-in creates the family (`backend/app/api/routes_auth.py`)
- Parent home: per-kid balance, add/deduct with a note, "+ Add a kid"
- Kid portfolio: holdings, cash available, day change; Buy tab (catalog) / sell from a holding
- Buy flow: amount↔units toggle with a live server-computed quote, insufficient-funds guard
- 20 stocks + 5 baskets (incl. TA35.TA, ^STOXX) seeded via Alembic
- Prices + FX refreshed together by one scheduler job hit via `POST /internal/refresh`
  (wire this to Vercel/Railway Cron 4-5x/day in production — see backend README)
- Family base-currency setting (`/home/settings`)
- PWA manifest + minimal service worker for "Add to Home Screen"

**Explicitly out of scope for v1** (see spec section 4.1 / architecture
section 6): kid login, co-parent accounts, recurring allowance rules,
per-viewer display currency, billing.

**Flagged for pre-launch, not yet needed** (spec 4.2): a children's-data
privacy policy — required once this is public and collecting data about
minors, even without real money involved. Not blocking for building/
testing, but don't launch publicly without it.

## Verified so far

- Backend: all modules import cleanly, migrations render valid SQL
  end-to-end (schema + seed), the Yahoo price/FX client was smoke-tested
  against live data.
- Frontend: `npm run build` and `npm run lint` both pass clean; the
  landing page and all four app screens were visually verified against
  the design handoff with real rendering (screenshots), pixel-close to
  the mocks.
- **Not yet verified**: the full authenticated flow end-to-end (sign-in
  → create family → add a kid → buy/sell) against a real Postgres
  database and real Google OAuth credentials, since those need the
  values described above. Worth doing once you've plugged those in.
