# FamilyBank — Handoff / Orientation

Read this first. `FamilyBank_spec.md` and `FamilyBank_architecture.md` are
the product/architecture source of truth; `design_handoff_familybank/`
has the visual design. This file is session-to-session state: what's
built, what's verified, what's not done, and the non-obvious lessons
learned while building it — read it before starting new work, and update
it when you finish a session of meaningful work (especially if you hit
and fixed a real bug — the "Lessons learned" section exists so the next
session doesn't reintroduce it).

## What this is

Parents track allowance/debt owed to their kids; kids "invest" that
virtual balance in real stocks/indices at real market prices. No real
broker, no real money movement — see spec section 0 for the framing that
has to stay sharp on every screen.

```
backend/    FastAPI + SQLAlchemy + Postgres (Neon) — see backend/README.md
frontend/   Next.js 16 (App Router) + Tailwind v4 — see frontend/README.md
```

## Status as of 2026-09-03

**Built and verified:** the full v1 flow — Google-only sign-in →
onboarding (currency + first kids) → home (balances, add/deduct) → kid
portfolio (holdings, since-purchase %, sell) → buy flow (units/amount
toggle with a live server-computed quote, snapped to a real tradable
step size) → per-kid history (general + investment-only, now currency-
and source-aware — see below) → settings (currency, kid management,
**real currency conversion with a warning dialog**). 65 backend tests
pass (`cd backend && pytest`), frontend `npm run build`/`npm run lint`
are clean.

**History now shows every row in the currency it was actually recorded
in, plus a running balance and the source of each change (built
2026-09-03).** A parent hit this for real right after the currency-
change feature below shipped: an old 200 EUR deposit displayed as
"200 ILS" after converting to ILS, because every row was formatted with
the family's *current* currency instead of whichever currency was
active when it was recorded — `debt_transactions.amount` has no
per-row currency (see "Lessons learned"). Fixed in
`debts_db_service.list_transactions_with_currency` (used by
`GET /kids/{id}/debt`): walks a kid's ledger oldest-to-newest and flips
the tracked currency at each `is_adjustment` row, which now records its
own `from_currency`/`to_currency` (migration 0006). Also added:
- **Balance before/after per row**, so a currency-conversion row reads
  as "was €182.86 → now ₪638.60" instead of just a bare amount — this
  is what actually makes a cross-currency row legible.
- **`is_investment`** on the debt row `buy()`/`sell()` write alongside
  a real investment transaction, so history shows "Bought"/"Sold"
  instead of a generic "Added"/"Deducted" indistinguishable from a
  parent manually changing the balance.
- **Migrations 0007/0008 backfill both of the above** for rows written
  before migration 0006 existed (parsed from each row's own note text,
  e.g. "Currency changed: EUR → ILS" or "Bought 0.008 units of QQQ") —
  a new nullable column has no way to backfill data it never captured,
  so every *existing* adjustment/buy/sell row would otherwise have kept
  reading as NULL/false forever. `debts_db_service._adjustment_currencies`
  also has a note-parsing runtime fallback for the same reason, so a
  database that hasn't run 0007/0008 yet degrades gracefully instead of
  the endpoint 500ing (which is exactly what happened before this fix —
  see "Lessons learned").
- **Known limitation, not addressed:** if a currency change nets to
  exactly zero for a kid (e.g. their balance happened to be 0 at that
  moment), `apply_currency_conversion` skips writing them an adjustment
  row (would be a no-op) — but `list_transactions_with_currency` uses a
  kid's *own* adjustment rows to know when their currency changed, so
  that kid's older rows (if they have prior history that nets to zero)
  keep reading as today's currency forever instead of the one they were
  actually recorded in. Rare and left unaddressed; fixing it properly
  means tracking currency changes at the family level independent of
  any one kid's balance.

**Currency change now actually converts balances, not just relabels
them (built 2026-08-21).** Previously, switching a family's currency in
Settings just flipped `base_currency` — a ₪36 debt silently became "$36"
after switching to USD instead of the correct ~$10, because
`debt_transactions.amount` has no per-row currency (it's implicitly
"whatever `family.base_currency` is right now"). Also, the FX rate cache
only warmed pairs for currencies already in use, so the first family to
pick a currency nobody had used yet had no rate to convert with. Fixed:
- `app/core/currencies.py`'s `SUPPORTED_CURRENCIES` (mirrored in
  `frontend/lib/currencies.ts`) is now what the scheduler keeps warm
  against USD, not just currently-used currencies — see
  `scheduler/jobs.py`.
- `fx_service.get_rate`/`rate_from_table` triangulate through USD when
  no direct or inverse pair is cached (the scheduler only ever caches
  X↔USD, never X↔Y directly for two non-USD currencies).
- On `PATCH /family/settings`, when the currency actually changes,
  `debts_db_service.apply_currency_conversion` adds **one adjustment
  row per kid** sized so the balance converts correctly — existing
  history rows are never rewritten (a deliberate choice: rewriting would
  lose per-row provenance; an adjustment row keeps the ledger's audit
  trail intact and is visible in the kid's history with a note
  explaining what happened). Investment holdings needed no equivalent
  fix — they already store their own currency and convert at read time.
- New `GET /family/settings/currency-preview?to=XXX` backs a
  confirmation dialog (`currency-change-sheet.tsx`) that shows each
  kid's real old→new balance before the parent commits — this is
  presented as a rare, deliberate action, not a silent instant switch.
- **Known limitation, not addressed:** no row locking on the family
  during the conversion. Two concurrent `PATCH /family/settings` calls
  for the same family (e.g. two devices open to Settings at once) could
  both read the old currency before either commits and double-apply the
  conversion. Low blast radius (a parent would notice and could just
  change currency again) and no other write path in this codebase locks
  rows either, so this was left as-is rather than adding
  `SELECT ... FOR UPDATE` for a rare, human-paced action — but worth
  knowing if this ever needs to become bulletproof.

**Deployed and confirmed working** (signed in and tested live on a phone,
2026-08-20):
- Frontend: https://family-bank-nine.vercel.app (Vercel, root directory
  `frontend`, auto-deploys from `master`)
- Backend: https://familybank-backend.onrender.com (Render, deployed via
  `render.yaml` at repo root, auto-deploys from `master`)
- **`master` is the deploy branch for both.** Pushing to `master` on
  GitHub redeploys both services automatically. Work on a feature/worker
  branch and merge to `master` when it's ready to go live — don't expect
  a `worker-N` branch to be reachable in production until it's merged.
- Env vars live in each platform's dashboard (Render: service →
  Environment; Vercel: project → Settings → Environment Variables), not
  in the repo. If you add a new required env var, you need to add it in
  both the relevant local `.env`/`.env.local` *and* the dashboard, or
  production will break silently on next deploy.
- Render free tier sleeps after 15 min idle — first request after that
  can take 30-50s. Not a bug if something seems slow after a break.

**Not yet done:**
- Google OAuth client is still in "Testing" mode (Google Cloud Console)
  — only test users you've explicitly added can sign in. Needs Google's
  verification review before public launch.
- Children's-data privacy policy — flagged in spec 4.2 as a pre-launch
  requirement, not needed to keep building.
- See `TODO.txt` at repo root for the user's own running feature-idea
  list (currency-change UX, pocket money, safety, co-parent sharing,
  native app, kid login, multi-kid competitions). That file is
  intentionally left untracked/uncommitted — it's scratch notes, not
  part of the build.

## Running locally

```bash
# backend
cd backend && .venv/Scripts/activate
uvicorn app.main:app --reload --port 8001

# frontend (separate terminal)
cd frontend && npm run dev
```

Both need `.env`/`.env.local` filled in — see each README. The backend
now runs its own in-process scheduler (refreshes prices/FX every 5h
automatically, logs when it does) — you don't need to manually trigger
`/internal/refresh` in normal dev, only if you want fresher data sooner.

### Database: dev/test branch vs. production

There are now two separate Neon branches — **use the dev/test one for
everything except the deployed app itself**:

- **Production** (`ep-crimson-wildflower-...`) — only Render's
  `DATABASE_URL` env var should point at this. Never put it in a local
  `.env`; you shouldn't need to touch it directly at all.
- **Dev/test branch** (`ep-autumn-violet-...` as of 2026-09-03 — this
  has already changed hostname once, when the original `ep-purple-mud-...`
  branch's password stopped working and the user cut a fresh Neon
  branch; **don't hardcode the hostname anywhere, always read it from
  `backend/.env`**, and don't be surprised if it's changed again by the
  time you read this) — what `backend/.env` points at locally, and what
  all local/worktree work and the pytest suite should run against.
  Created as a Neon branch (copy-on-write snapshot) from production, so
  its schema is current (migrations applied through 0008 as of this
  writing) and it happens to contain a *copy* of what was real family
  data at branch-creation time — that copy is now fully independent of
  production, so it's fine to modify or delete during testing. If you
  need the exact connection string, ask the user (it's in
  `backend/.env`, which is gitignored — never committed) rather than
  guessing at the hostname. Note the connection string Neon's dashboard
  hands you is `postgresql://...` — this project needs the async driver,
  so it must be edited to `postgresql+asyncpg://...` (and the
  `channel_binding`/`sslmode` query params dropped, since asyncpg
  doesn't parse them the way libpq does) before it'll work here.

Within the dev/test branch:

1. **Prefer the isolated synthetic test family** for ad-hoc/manual
   testing over the copied real-looking one:
   `family_id=00000000-0000-0000-0000-000000000001`,
   `user_id=00000000-0000-0000-0000-000000000002`. Mint a session JWT
   for it with `issue_session_token` and test against that — keeps your
   scratch data recognizable and separate from the copied family data.
2. **The pytest suite is safe to run here** (and would have been safe
   against production too, for the same reason) — every test runs
   inside one outer transaction rolled back at teardown
   (`tests/conftest.py`, SQLAlchemy `join_transaction_mode="create_savepoint"`),
   so nothing persists either way. Documented here mainly so you don't
   *assume* it's unsafe and avoid running it.

**Every worktree needs its own `backend/.env` / `frontend/.env.local`**
— they're gitignored, so a fresh worktree checkout won't have them.
Copy from `.env.example` and fill in the same dev/test `DATABASE_URL`
(ask the user for it), or copy the values from another already-working
worktree/checkout.

## Lessons learned this session (don't reintroduce these)

- **`sqlalchemy.Enum(SomePyEnum)` binds by the Python member's `.name`
  ("ADD"), not `.value` ("add"), by default.** Every enum column needs
  `values_callable=lambda e: [m.value for m in e]` or asyncpg will
  reject writes with a data-type error the moment real data flows
  through (psycopg2 is more lenient here, which is why this kind of bug
  survives review and only shows up against a real driver).
- **`func.case(...)` is wrong** — `case()` is a standalone SQLAlchemy
  construct (`from sqlalchemy import case`), not a function under
  `func`. `func.case(...)` silently builds a nonsense SQL function call
  instead of erroring at import time.
- **FastAPI dependency chains autobegin transactions.** Any
  `Depends(get_kid)` / `Depends(get_family)` that does a `db.get(...)`
  opens a transaction before your route body runs. A shared
  `transaction()` helper that does `if session.in_transaction(): yield;
  return` (skip wrapping) will silently never commit in that case — use
  a SAVEPOINT (`begin_nested()`) for the inner case instead, and keep
  explicit `db.commit()` calls at the route level regardless (see
  `app/core/db.py`'s `transaction()` docstring and `routes_investing.py`).
- **Neon's pooled endpoint + `pool_pre_ping=True` roughly doubles
  latency** — it's an extra round-trip on every single request. Use
  `pool_recycle` instead.
- **Global, rarely-changing reference data (the price/FX cache) should
  be cached in-process, not re-queried per request.** See
  `investing_service.load_price_context` / `clear_price_context_cache`
  — cleared automatically when the scheduler refreshes, so it can't
  serve stale-past-a-refresh data, with a 5-minute TTL as a safety net.
  **If you add a new module-level cache like this, you must also clear
  it in the `db_session` pytest fixture** (see `tests/conftest.py`) or
  tests will leak state into each other through the shared process.
- **Pydantic `Decimal` fields serialize as JSON strings**, not numbers —
  the frontend types in `lib/types.ts` reflect this; don't "fix" them to
  `number`.
- A kid's cash balance is *always* the signed sum of `debt_transactions`
  — never stored redundantly. Buy/sell write debt_transaction rows too
  (so the ledger is one source of truth); this is why you'll see
  `debts_db_service` imported from `investing_service`.
- **The FX cache only ever stores X↔USD pairs** (see `scheduler/jobs.py`)
  — never a direct pair between two non-USD currencies. Any code that
  converts between two arbitrary currencies must triangulate through
  USD (`fx_service.get_rate`/`rate_from_table` already do this); a naive
  direct-or-inverse-only lookup will raise/return `None` for a pair like
  EUR→ILS even though both convert fine individually via USD.
- **A DB column with no per-row currency field** (like
  `debt_transactions.amount`) is implicitly "whatever the family's
  currency is right now" — changing that currency without also writing
  a conversion adjustment silently corrupts every existing amount's
  real-world meaning. If you add another currency-denominated column
  without its own currency field, it has the same trap.
- **Adding a nullable column that new code assumes is "always set" will
  crash on every row written before the migration.** This actually
  happened: `is_adjustment`'s `from_currency`/`to_currency` and
  `is_investment` (migration 0006) left every pre-existing row with
  NULL/false forever — a migration that only adds a column has no way
  to backfill data it never captured — and the endpoint reading them
  500'd the moment a real user hit an old row. If new code needs a
  column populated on *every* row, either backfill existing rows in the
  same migration (or a follow-up one — see 0007/0008, which parse the
  same info back out of each row's own note text) or write the read
  path to degrade gracefully when it's NULL, ideally both.
- **A stuck/orphaned local dev server on Windows can survive `Stop-Process`
  reporting "process not found" while still actually answering
  requests** — `netstat -ano` kept showing a PID bound to a port that no
  process-enumeration tool (`Get-Process`, `Get-CimInstance`, `taskkill`)
  could find, and it kept serving *stale* code through several full
  restarts on that port. Cause unconfirmed; the fix was to stop fighting
  it and just move the dev server to a different port (update
  `frontend/.env.local`'s `BACKEND_URL`/`NEXT_PUBLIC_BACKEND_URL` to
  match) rather than trusting that a given port number is actually free
  just because you just killed everything you can see on it.

## Architecture quick-reference

- **Auth**: Google-only. NextAuth on the frontend gets Google's own
  `id_token`, POSTs it to backend `POST /auth/sync`, which verifies it
  directly against Google (never trusts the frontend), finds-or-creates
  the family, and returns a backend-issued session JWT. That JWT (not
  Google's) is what every other request carries — see
  `backend/README.md`'s "Auth flow" section.
- **Multi-tenancy**: every family-scoped query is filtered by
  `family_id` pulled from the verified JWT server-side, never from the
  request body/path. `backend/app/api/deps.py`'s `get_kid`/`get_family`
  are the enforcement point — a `kid_id` from another family 404s, it
  never leaks. This is the property `tests/test_api_family_isolation.py`
  exists to guard.
- **Currency**: prices/FX are fetched by one scheduler job (now genuinely
  automatic — `app/scheduler/loop.py`, runs every 5h in-process),
  4-5x/day, stored raw (native currency). Every read converts to the
  requesting family's currency at read time (`fx_service.py`). Nothing
  per-family or per-request ever calls Yahoo directly.
- **Unit steps**: buying/selling snaps to a "nice" tradable granularity
  so a purchase always costs something sensible (1-10 in the family's
  currency) — `investing_service.unit_step_for_price` /
  `round_to_step`. The frontend's `lib/format.ts`'s `defaultUnitStep`
  mirrors the same algorithm for the buy screen's stepper UI; keep them
  in sync if you touch either.

## If you're picking up work in a parallel worktree

You're likely one of several parallel Claude sessions, each in its own
`git worktree` on its own `worker-N` branch, all sharing this one repo's
history and — importantly — **the one Neon dev/test branch** (see
"Database: dev/test branch vs. production" above; this matters even more
with several sessions running at once). A few things specific to that
setup:

### Quick start (worktrees created 2026-08-20)

`backend/.env` and `frontend/.env.local` were pre-copied into each
worktree with **unique ports already assigned** so all three can run
their dev servers simultaneously without colliding:

| Worktree | Backend port | Frontend port |
|---|---|---|
| `FamilyBank-worker-1` | 8011 | 3011 |
| `FamilyBank-worker-2` | 8012 | 3012 |
| `FamilyBank-worker-3` | 8013 | 3013 |

First time in a given worktree, install deps (not shared across
worktrees — `.venv`/`node_modules` are gitignored), then start with the
matching port explicitly:

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port <your-backend-port>

cd frontend && npm install
npm run dev -- -p <your-frontend-port>
```

If a fourth worktree gets created later, pick the next port pair
(8014/3014, etc.) and update its `.env`/`.env.local` the same way.

- `master` is the trunk **and the deploy branch** (see "Deployed and
  confirmed working" above) — branch off it, merge back into it, and
  know that merging to `master` redeploys production for everyone.
  Coordinate before merging if your change touches something another
  worker is also mid-way through (schema/migrations especially — two
  workers both adding, say, "0005_*.py" will collide; check
  `alembic/versions/` for the latest number before naming a new one).
- Don't assume you're the only session running. If something in the DB
  looks different from what you expect (an extra migration applied, test
  data you didn't create), another worker probably did it — check
  `git log`/recent migrations before assuming it's a bug.
- Pull `master` before starting and periodically while working, so you
  merge from a recent base rather than discovering a large conflict at
  the end.
- There's deliberately no separate long-lived `dev`/staging branch below
  `master`; this project is small enough that the extra layer isn't
  worth it (see git history around 2026-08-20 if you want the
  reasoning). Check `git branch -a` if that's changed since this was
  written.
- Before calling anything done: run the backend test suite
  (`cd backend && pytest`), the frontend build+lint
  (`npm run build && npm run lint`), and — for anything touching a
  screen — actually look at it (Playwright screenshot against a
  throwaway preview route, or the real dev server) rather than trusting
  the code alone. This whole app was built that way; findings from
  actually running it caught several bugs static review missed.
- If your change touches the price/FX cache, the enum columns, or the
  transaction/autobegin pattern, re-read "Lessons learned" above first.
- Update this file's "Status" section when you finish, so the next
  session (or the next parallel worktree) starts from accurate ground
  truth instead of re-deriving it.
