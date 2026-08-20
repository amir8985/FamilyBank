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

## Status as of 2026-08-20

**Built and verified:** the full v1 flow — Google-only sign-in →
onboarding (currency + first kids) → home (balances, add/deduct) → kid
portfolio (holdings, since-purchase %, sell) → buy flow (units/amount
toggle with a live server-computed quote, snapped to a real tradable
step size) → per-kid history (general + investment-only) → settings
(currency, kid management). 48 backend tests pass (`cd backend && pytest`),
frontend `npm run build`/`npm run lint` are clean, and every screen has
been visually verified against the design handoff.

**Not yet done:**
- Not deployed anywhere. Runs locally only so far (backend :8001,
  frontend :3002 — port 8000/3000 are taken locally by unrelated
  projects on this machine; that's a local quirk, not relevant once
  deployed).
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

### The database is real, not a sandbox

There is no separate dev/test Postgres — everything points at the same
Neon instance the user's actual family data lives in. Two consequences:

1. **Never run ad-hoc scripts against the real family** to test
   buy/sell/debt flows. Use the isolated synthetic test family instead:
   `family_id=00000000-0000-0000-0000-000000000001`,
   `user_id=00000000-0000-0000-0000-000000000002` (created once, see
   git history for the setup script). Mint a session JWT for it with
   `issue_session_token` and test against that.
2. **The pytest suite is safe to run against this same real DB** — every
   test runs inside one outer transaction rolled back at teardown
   (`tests/conftest.py`, SQLAlchemy `join_transaction_mode="create_savepoint"`),
   so nothing persists. This was a deliberate, verified design — see the
   docstring in `conftest.py`.

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

- Branch off `dev` (or whatever the active integration branch is at the
  time — check `git branch -a` and ask if unclear), not `master`.
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
