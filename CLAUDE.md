# FamilyBank — Handoff / Orientation

Read this first. `FamilyBank_spec.md` and `FamilyBank_architecture.md` are
the product/architecture source of truth; `design_handoff_familybank/` has
the visual design. This file is session-to-session state — read it before
new work, update it after meaningful work (especially bugs fixed — the
"Lessons learned" section exists so the next session doesn't reintroduce
them). **This is a condensed version (2026-09-09)** — full narrative/
reasoning for anything summarized here is in `git log`; if a bullet here
doesn't give you enough to proceed safely, check the file's git history
before guessing.

## Talking to the user

The user skims, doesn't read top-to-bottom. End every response with a
short plain-language summary of what changed/is blocked/needs a decision,
placed last, not only at the top.

**Always reply to the user in English**, even when they write in Hebrew.

## What this is

Parents track allowance/debt owed to their kids; kids "invest" that
virtual balance in real stocks/indices at real market prices. No real
broker, no real money movement — see spec section 0 for the framing that
must stay sharp on every screen.

```
backend/    FastAPI + SQLAlchemy + Postgres (Neon) — see backend/README.md
frontend/   Next.js 16 (App Router) + Tailwind v4 — see frontend/README.md
```

## Current status (as of 2026-09-10)

**`kid-pages` is merged to `master`** (backend `1.9.0`, frontend `0.10.0`
at merge). The whole "Kid login + kid-facing app" section below is now
live, not in-flight.

**Server-version display — merged on top (backend `1.9.1`, frontend
`0.10.1`).** `/health` now returns `{"status","version"}` (`version` is
`app.version`, mirroring the FastAPI `version=` — single source, nothing
hardcodes it elsewhere). Settings footer: `components/app-version.tsx`
(client) shows `v<frontend>` by default (dotted underline, tappable) and
reveals a second dimmer line `server v<api>` below it on tap — tap the
version again to collapse. Fetches `/health` from
`NEXT_PUBLIC_BACKEND_URL` only on first reveal; a failed fetch shows
"unavailable" and doesn't retry (fine for a footer). `test_health.py`
covers the endpoint. Kept deliberately minimal per user: just the two
version numbers, hidden by default so the footer stays quiet.

**`perf-followups` — Cloud Run migration groundwork (worker-1).** The
*code* landed on `master` 2026-09-09 (`scheduler/jobs.py`: a Postgres
session-level advisory lock around `run_refresh()` so overlapping
triggers don't double-write `price_ticks` — the lock session must hold
its connection for the whole refresh, don't add a `commit()`; plus
`spawn_refresh_if_stale(prices_as_of)`, a best-effort catch-up refresh
`/home`+`/catalog` fire when cached prices are older than
`refresh_staleness_threshold_hours` — insurance for a missed external
cron, disabled in tests via `set_stale_fallback_enabled` + an autouse
fixture). **The GCP move itself is not done** — project, Artifact
Registry, first deploy, Cloud Build trigger, Cloud Scheduler jobs,
monitoring alert, the frontend URL cutover, decommissioning Render — all
in `docs/cloud-run-migration.md`, gated on user action. Replacing the
Yahoo price fetch is deliberately sequenced after that migration.

Shipped, in order, each reviewed + tested + Playwright-verified against
the dev server + synthetic test family (`family_id
00000000-0000-0000-0000-000000000001`):

1. **Core v1** (sign-in → onboarding → home → kid portfolio → buy →
   history → settings), currency conversion with real balance conversion
   + per-row currency history, launch-compliance (privacy/terms pages,
   consent gate, `users.consent_accepted_at`).
2. **Request/perf logging** (`request_logs` table, `RequestLoggingMiddleware`,
   `/internal/client-metrics` client-timing beacon) + the resulting
   perf investigation (see "Production performance" below).
3. **Stock boost feature**: family-wide `boost_buffer_rate` that adds to
   a stock's return only on up-ticks; per-lot purchases (`investment_lots`,
   replacing avg-cost `investment_holdings`); `price_ticks` table for
   since-purchase history; sell-and-rebuy migration endpoint for changing
   the rate with open positions.
4. **Instant UX**: client-side `/home` store + optimistic writes, no more
   full-page freezes on slow backend.
5. **Savings plans**: parent-defined savings plans (flexible/locked) a
   kid can move cash into, compounding monthly.
6. **Kid login + kid app** (merged to `master` 2026-09-10): kids get
   their own `/kid` area — invite = link + spoken PIN, one-time entry,
   silent thereafter.
7. **Server-version display** (2026-09-10): `/health` returns the API
   version; Settings footer reveals it under the frontend version on tap.

### Savings plans — what it is and key decisions

One unified `savings_plans` model — a plan is **flexible**
(`lock_months == 0`, withdraw any time) or **locked** (`lock_months > 0`,
locked until maturity, then keeps compounding until withdrawn). Settings:
Settings → *Advanced investing & savings* → *Flexible savings* /
*Locked savings*. Kid sees it on portfolio screen, tabs
Portfolio/Invest/Save.

- Every `SavingsDeposit` **snapshots** its plan's name/rate/lock_months at
  deposit time (`plan_id` is `ON DELETE SET NULL`) — editing/deleting a
  plan never changes money already in it.
- `savings_service` is **stateless**, like `boost_service`: value =
  `principal * (1 + rate/100) ** (elapsed_days / 30.4375)`, recomputed on
  every read, no accrued-interest column, no cron.
- Withdrawals are **whole-deposit-only** — closes the deposit, pays
  principal+interest via a `debt_transactions` row with `is_savings=true`
  ("Moved to savings" / "Savings payout" in history).
- Recommended presets in `savings_service.PRESET_PLANS` (code, not
  seeded) — changing a preset constant does **not** retro-change plans
  already switched on from it.
- Settings pages are a **staged form** — checkboxes stage, a sticky "Save
  changes" bar commits. If a save switches a plan **off** while it still
  holds a deposit, `SavingsLeftoversSheet` opens with per-kid breakdown +
  *Cash out* / *Switch back on*.
- **Cash-out** (`POST /family/savings-plans/{id}/cash-out`) closes every
  open deposit in a plan across all kids, back to cash — overrides the
  maturity lock (parent's own money). No page-wide "cash out everything".
- Parent confirms use `ConfirmSheet` (amber, `--color-tint-brass`), not
  `window.confirm()`. Kid-side withdraw still uses native `confirm()`.
- Hub status pills per kind: green Active / brass Deactivated / red "N
  still growing" (leftovers in an off plan).
- `annual_rate` shows the *compounded* yearly equivalent next to the
  monthly rate — keep `savings_service.annual_rate` and frontend
  `lib/format.ts` in sync.

Migrations `0012_savings_plans`, `0013_savings_plan_preset_key` — shared
dev DB is on `0013`.

**Non-obvious:**
- `plan_deposit_breakdown` must aggregate **per kid, not per deposit**
  (React duplicate-key bug otherwise — `SavingsLeftoversSheet` and the
  cash-out `ConfirmSheet` key lists by `d.kid_id`).
- `savings-kind-form.tsx`'s staged-state reset uses the adjust-during-
  render pattern (`if (sig !== lastSig) { setLastSig; setOverride({}) }`)
  — don't "fix" into `useEffect` (trips lint + wrong tool).
- `investing_service` imports `savings_service` (for `savings_value` in
  `get_portfolio`); `savings_service` only imports `debts_db_service` /
  `fx_service` — no cycle, keep it that way.

**Known gaps (not bugs):**
1. **Home screen doesn't show savings** — a kid's `/home` view shows
   $100 less cash after a deposit with no savings line anywhere on that
   screen (only on their detail page). **#1 follow-up.**
2. Deposit/withdraw POSTs re-fetch full deposit detail (incl. chart
   series) that the frontend then discards — minor waste.
3. Mixed-currency summation assumes a cached FX rate exists for a
   deposit's currency (same tolerance as `investing_service` elsewhere).
4. Pre-deposit "Locked until ~date" uses calendar-month math vs. backend's
   30.4375-day math — off by a day or two, copy says "about".

### Kid login + kid app — what it is and key decisions

Kids get their own way in (spec 4.1 v2). **Auth model, decided with the
user over three iterations:** parent generates a per-kid invite = a
shareable **link** + a short **PIN** the parent reads aloud (two
channels, so a leaked link is useless alone). The link is **multi-use
for 24h** — the kid opens it on their phone *and* their laptop, all one
account. After that they're signed in for good on those devices.

- **`kids.token_version`** (int) is the revocation lever, bumped ONLY by
  the parent's explicit **"Sign <name> out of all devices"**
  (`POST /kids/{id}/sign-out-all`, `kid_auth_service.sign_out_all`) — for
  a lost phone. An ordinary claim does NOT bump it (claiming is additive
  — another device, same account). The kid JWT embeds the value it was
  minted with; `deps._resolve_kid_and_family` (the single isolation checkpoint for `get_kid`/`get_kid_and_family`/`get_current_kid`) 401s a token whose
  `tv` no longer matches.
- **`kids.public_id`** (opaque 16-hex handle, `_new_public_id`): what
  appears in every kid URL (`/kid/kids/<public_id>`) — the primary key is
  never exposed. Backend `/kids/{kid_id}/*` routes take `kid_id` as
  `str`; `_resolve_kid_and_family` accepts a real UUID (parent token) or the
  kid's own uuid/public_id (kid token — the token names the kid, the
  path segment is cosmetic but must still name *this* kid or it 404s
  like the cross-family case). One JOIN gets kid+family in a round-trip
  for both token kinds.
- **`kids.sessions_active`** (bool): true once any device has claimed,
  false after sign-out-all. Drives whether Settings shows the sign-out
  button.
- **`kid_invites`** (one row per kid, replaced on regen): `claim_token_hash`
  (plain SHA-256 — token is high-entropy), `pin_salt`+`pin_hash` (PBKDF2),
  `failed_attempts` (burns the invite at `kid_claim_max_attempts`=5),
  `expires_at` (`kid_invite_ttl_hours`=24), `first_claimed_at`
  (informational — **multi-use**, never blocks). Wrong-PIN path
  **commits** `failed_attempts++` before raising.
- **Kid JWT**: `role:"kid"`, `kid_id`, `tv`. TTL `kid_jwt_ttl_days`=365
  (long on purpose — re-auth means a parent has to act). Minted by
  `POST /kid-auth/claim` (unauthenticated + coarse per-IP rate limit).
- **Backend authz**: `deps.get_kid`/`get_kid_and_family` resolve via
  `_resolve_kid_and_family` (one JOIN, one place to audit — sibling / hand-edited cross-kid URL → 404, stale/foreign kid token → 401).
  `deps.get_family`
  **rejects kid tokens outright** (covers all `/family/*`, `/home`,
  savings-plan mgmt in one place); `get_family_currency` is the kid-OK
  variant for the read-only `/catalog`. `require_parent` guards
  `POST /kids`, `DELETE /kids/{id}`, `POST /kids/{id}/debt` (kids must
  never add money), `POST/GET /kids/{id}/invite`. Kid-reachable:
  portfolio, buy/sell/sell-all/quote, savings deposit/withdraw/overview,
  `GET /kids/{id}/debt` (history), investment-transactions, catalog.
- `PortfolioOut` now carries `boost_buffer_rate` (was a separate
  `/family/settings` call the buy screen made — kids can't call that).
- **Frontend sharing**: `useFamily()` (FamilyStore) gained `token` +
  `basePath` (`/home` | `/kid`) + `isKid`. Parent `FamilyProvider` sets
  them from NextAuth + `/home`; new **`KidFamilyProvider`**
  (`lib/kid-family-store.tsx`) implements the same shape for one kid,
  seeded from `/kid/me` (resolved server-side in the kid layout, passed
  as a plain object) + `/kids/{id}/portfolio`. Every shared component
  (`portfolio-client`, buy/sell/savings flows, history pages,
  `lot-detail`) was switched from `useSession()` → `useFamily().token`,
  and their per-kid hrefs go through **`useKidLinks(kidId)`**
  (`{pagePrefix, portfolio, home}`) — because the kid app's "home" is
  `/kid/kids/<id>` and its portfolio is `/kid/kids/<id>/portfolio`,
  whereas the parent's portfolio IS `/home/kids/<id>`. Same components,
  both apps.
- **Kid routes** (`app/kid/`): `kids/[kidId]/` (the `[kidId]` param
  carries the **public_id**, not the pk — kept as `[kidId]` only so the
  parent-page re-exports' `params.kidId` access still works) has its own
  auth-guard `layout.tsx` (per-kid cookie + awaited `/kid/me`, 401/403 →
  `/kid/locked?revoked=1`, `identity.public_id !== url` → own kid);
  `kids/[kidId]/page.tsx` = `KidHome`, `/portfolio` = `KidPortfolioScreen`,
  the rest are 1-line re-exports of the parent pages. `/kid` (bare) =
  `KidLanding`: 0 sessions → locked, else redirect to the `kid_last`
  cookie's kid (or the first session) — **no picker** (each kid keeps
  their own `/kid/kids/<handle>` link). `/kid/join/[token]` and
  `/kid/locked` sit outside the guarded subtree.
- **Kid session storage**: **per-public_id** httpOnly cookie
  `kid_sess_<public_id>` (NOT one shared cookie — siblings on one device
  / two browser tabs must not clobber each other; Chrome shares its
  incognito cookie jar, so a single cookie name really does merge them).
  Set by `app/kid/api/claim`, cleared by `.../signout` (needs
  `{publicId}` in the body). Plus a non-httpOnly `kid_last` hint so bare
  `/kid` skips straight to the right kid. In the kid app the frontend
  uses `public_id` as the kid id *everywhere* (URLs, cache keys, API
  paths — backend resolves it from the token); the real UUID never
  leaves `/kid/me`.
- **Parent UI**: Settings kid row → name + "Remove" on top, a prominent
  full-width **"Link a device ›"** below → `AttachChildSheet` (generate
  link + PIN; copy-link always + `navigator.share` when available; a
  red **"Sign <name> out of all devices"** button when `sessions_active`).
- **Parent freshness**: `FamilyProvider` now also **polls `/home` every
  30s while the tab is visible** (paused when hidden) — so a parent
  watching `/home` sees a kid's trade land without a manual refresh
  (the client store otherwise only reconciled on nav / tab-refocus).

Migrations `0014_kid_auth` (`kids.token_version`, `kid_invites`) +
`0015_kid_public_id_multi_device` (`kids.public_id`, `kids.sessions_active`,
`consumed_at`→`first_claimed_at`). Shared dev DB is on `0015`.

**Local dev ports drifted this session** (Windows ghost-port bug, hit
again on `8101` then `8102` — see Lessons learned): backend `8103`,
frontend `3015`. `backend/.env` `CORS_ORIGINS` lists `3015` first (so
`frontend_origin` = the claim-link host resolves to `:3015`);
`frontend/.env.local` `BACKEND_URL`/`NEXT_PUBLIC_BACKEND_URL` → `:8103`.
Check `netstat`/`.env` for ground truth before trusting this.

**Non-obvious:**
- `KidInvite` datetime columns MUST be `DateTime(timezone=True)` in the
  model (not bare `Mapped[datetime]`) or asyncpg rejects the tz-aware
  `expires_at` insert against the `timestamptz` column.
- A multi-use link means a leaked link+PIN lets someone in for up to 24h
  (and they keep the session after). Mitigation is the parent's "sign
  out of all devices". Accepted for v1 (virtual money, low stakes).
- The kid app still lives under the root `SessionProvider` (NextAuth) —
  `useSession()` just returns null there; shared components no longer
  read it. Don't re-introduce a `useSession()` call in a shared component.
- The kid layout **awaits** `/kid/me` (unlike parent `home/layout.tsx`
  which must not await `/home`) — it's one fast query every kid route
  needs, and awaiting server-side is the only place a revoked-session
  401 can be caught with its `ApiError` type intact (a server→client
  promise rejection loses the type → generic error boundary).
- PWA `manifest.ts` `start_url` is still `/home` (parent-first). A
  dedicated kid Android app (worker-2's TWA) would point its own start
  URL at `/kid`.

**Known gaps (not bugs):**
1. Kid JWT has a fixed 365d expiry (no refresh) — a kid who doesn't open
   the app for a year needs a fresh link. Accepted for v1.
2. Per-kid `loading.tsx`/`error.tsx` not copied into the `/kid` tree
   (falls back to nearest boundary).
3. Kid-side sell/withdraw still uses native `confirm()` (consistent with
   pre-existing kid-portfolio behavior).
4. Bare `/kid` with 2+ sessions and no `kid_last` cookie picks the first
   arbitrarily. Fine in practice — each kid uses their own
   `/kid/kids/<handle>` link and `kid_last` is set on every home load.

### Instant UX (client-side store + optimistic writes)

Motivated by: "when I deduct money, show it done and save in the
background; Settings should just open while it thinks." Every `/home/*`
page was previously a blocking Server Component `await`, and writes did
`POST` then `router.refresh()` (2nd full round-trip).

- **`src/lib/family-store.tsx`** (`FamilyProvider`/`useFamily()`): holds
  the `/home` payload client-side for the session. **Seeded from a
  server-started, un-awaited promise** (`home/layout.tsx` does
  `api.get("/home", token)` with no `await`), read via React `use()`
  inside the provider's **own** `<Suspense>` — NOT awaited in the layout
  body (that reintroduces the navigation-blocking trap; see Lessons
  learned). Exposes `refreshHome()` + inverse-patch optimistic mutators
  (`applyKidBalanceDelta`, `addKidOptimistic`, `removeKidOptimistic`,
  `applyCurrencyOptimistic`), each returning a composable `rollback()`.
- **`src/lib/use-cached-resource.ts`**: stale-while-revalidate cache for
  per-kid detail (portfolio, catalog, history) not in `/home`.
  `invalidateResource(keyOrPrefix)` after a write; `invalidateKid()`
  helper drops the standard per-kid keys (extend it when adding a new
  per-kid cache key, e.g. savings did).
- **`src/components/ui/toast.tsx`**: surfaces optimistic-write failures
  (sheet already closed by the time a failure could show inline).
- Add/deduct, add/remove kid, sell, currency change: optimistic + close
  immediately, POST in background, `refreshHome()` to reconcile, toast +
  rollback on failure. Buy keeps its "Buying…" button (deliberate
  action, real server quote) but invalidates cache instead of
  `router.refresh()`.
- Auth guard (`requireSession()`, cookie-only) moved into
  `home/layout.tsx`'s body since pages below are now Client Components.
- Backend: `prices_as_of` (nullable datetime, from `PriceContext`, no
  extra query) added to `/home`+`/portfolio` responses so clients can
  cache price-derived screens with confidence.
- Also merged with `origin/master`'s stock-boost feature the same
  session — see git log for the merge-conflict resolution notes if
  touching `investing_service.py`/`routes_investing.py`/`SellControls`
  around this period.

### Stock boost feature

Family-wide `boost_buffer_rate` (monthly %, `families.boost_buffer_rate`)
that only ever *adds* to a stock's return on an up-tick — real downside
untouched. `price_ticks` (append-only, one row/symbol/scheduler refresh)
makes reconstructing a stock's path since purchase possible.
`investment_lots` replaced avg-cost `investment_holdings` for all new
buys (unifies boosted/unboosted under one per-lot model); two purchases
of the same symbol are separate, independently-sellable lots. Legacy
`investment_holdings` rows still sell via the old code path
(`investing_service.sell()` dispatches on `lot_id` vs `symbol`).

- `boost_service.py` is **stateless** — a lot's whole trajectory is
  recomputed on every read by walking `price_ticks` from `purchased_at`.
  Only viable at this app's scale (a family has a couple dozen open lots
  max); don't copy this pattern with real per-user volume.
- Rate can only change while **every** kid holds zero stock
  (`investing_service.has_open_positions`, enforced in
  `PATCH /family/settings/boost-buffer-rate`) — OR via
  `POST /family/settings/boost-buffer-rate/sell-and-rebuy`
  (`apply_boost_rate_change_with_rebuy`): snapshots every position,
  sells everything, changes the rate, rebuys — one outer commit makes it
  atomic.
- Settings UI: hub (`/home/settings/investing`) → sub-page
  (`/home/settings/investing/boost`, `boost-settings-form.tsx`) with
  toggle, rate stepper, worked example. Lot detail/sell/chart:
  `/home/kids/[kidId]/lots/[lotId]` (`lot-chart.tsx`, plain inline SVG).
  A closed lot (units=0 after full sell) shows its captured sale
  value/price, not a recomputed $0.
- Portfolio-wide "Sell everything" (`POST /kids/{id}/sell-all`) is the
  only sell action with a native `confirm()` (rest use in-app sheets).
- Deferred by explicit user request: "interest from parent" (flat
  monthly rate on cash, competing with the boost) — not built.

### Production performance investigation

Root cause: **per-query network latency to Neon (~300-450ms floor per
query, roughly constant regardless of query complexity), multiplied by
however many queries an endpoint runs sequentially** — points at
Render/Neon region mismatch (confirmed by user, **not yet fixed** — needs
a dashboard region decision, not a code change). Can't fix by
`asyncio.gather`-ing queries within a request: `AsyncSession` isn't safe
for concurrent use, and opening a second connection mid-request would
break test isolation (`tests/conftest.py`'s uncommitted-outer-transaction
strategy). Fix applied instead: fewer round-trips, not parallel ones —
`app/api/deps.get_kid_and_family` (one JOIN replacing two point-lookups,
swapped in everywhere both were needed), `load_price_context` now one
`LEFT JOIN` instead of two `SELECT`s, `POST /kids/{id}/debt` no longer
re-queries balance after insert (computes `balance_before ± amount` in
Python — also fixes a race-condition mislabeling bug the old re-query
had). Added `time_to_first_query_ms` (stdout-only, not persisted) to
confirm/rule out connection-acquisition overhead vs. query cost — check
it on slow single-query requests before assuming further causes.
`request_logs` now has retention (30d default, piggybacked on the
scheduler refresh). `/internal/client-metrics` is rate-limited (30/60s
per IP, in-memory — needs `--proxy-headers` in `render.yaml` to see real
client IPs behind Render's proxy) since it has no auth/shared secret by
design. Frontend: `loading.tsx`/`error.tsx` added to every `/home` and
`/onboarding` route segment; `home/layout.tsx`'s onboarding check moved
into a Suspense-wrapped `OnboardingGate` (a layout doing a blocking fetch
in its body blocks every route below it — see Lessons learned).

Scale review findings not yet acted on: single Render instance/uvicorn
process (fine at current traffic); in-process scheduler assumes exactly
one instance (needs leader election or the external-cron model before
adding a 2nd instance); connection pool unconfigured (SQLAlchemy default
5+10); free tiers (Render+Neon) aren't built for real scale regardless of
code — needs a paid-tier decision from the user, not flagged as urgent.

### Deployed

- Frontend: https://family-bank-nine.vercel.app (Vercel, root dir
  `frontend`, auto-deploys from `master`).
- Backend: https://familybank-backend.onrender.com (Render, `render.yaml`
  at repo root, auto-deploys from `master`).
- **`master` is the deploy branch for both** — a `worker-N` branch isn't
  live until merged. Env vars live in each platform's dashboard, not the
  repo — add new required vars in both the dashboard and local `.env`.
- Render free tier sleeps after 15 min idle (30-50s cold start) — not a
  bug if something's slow after a break.
- `TODO.txt` at repo root is the user's own untracked feature-idea
  scratch list — not part of the build, don't rely on it being there.

## Architecture quick-reference

- **Auth**: Google-only. NextAuth gets Google's `id_token`, POSTs to
  backend `POST /auth/sync`, which verifies directly against Google,
  finds-or-creates the family, returns a backend-issued session JWT —
  that JWT (not Google's) is what every other request carries.
- **Multi-tenancy**: every family-scoped query filters by `family_id`
  from the verified JWT server-side, never the request body/path.
  `app/api/deps.py`'s `get_kid`/`get_family`/`get_kid_and_family` are the
  enforcement point (a `kid_id` from another family 404s) —
  `tests/test_api_family_isolation.py` guards this property.
- **Currency**: prices/FX fetched by one in-process scheduler job
  (`app/scheduler/loop.py`, every 5h), stored raw (native currency).
  Every read converts to the requesting family's currency at read time
  (`fx_service.py`). The FX cache only stores X↔USD pairs — anything
  converting two non-USD currencies must triangulate through USD.
  Nothing per-family/per-request calls Yahoo directly.
- **Unit steps**: buy/sell snaps to a "nice" tradable granularity
  (`investing_service.unit_step_for_price`/`round_to_step`, mirrored in
  frontend `lib/format.ts`'s `defaultUnitStep` — keep both in sync).
- A kid's cash balance is *always* the signed sum of `debt_transactions`
  — never stored redundantly. Buy/sell write debt_transaction rows too.

## Running locally

```bash
# backend
cd backend && .venv/Scripts/activate
uvicorn app.main:app --reload --port <your-port>

# frontend (separate terminal)
cd frontend && npm run dev -- -p <your-port>
```

Both need `.env`/`.env.local` filled in (gitignored — copy from
`.env.example`, ask the user for `DATABASE_URL`). Backend runs its own
scheduler (refreshes prices/FX every 5h) — no need to manually hit
`/internal/refresh` in normal dev.

### Database: dev/test vs. production

Two Neon branches — **use dev/test for everything except the deployed
app**:
- **Production**: only Render's `DATABASE_URL` should point here. Never
  put it in a local `.env`.
- **Dev/test branch**: what `backend/.env` points at locally (hostname
  has changed before and may again — always read it from `backend/.env`,
  never hardcode it; ask the user for the connection string if needed,
  it's gitignored). Copy-on-write snapshot of production, now fully
  independent — safe to modify/delete. Connection string from Neon's
  dashboard is `postgresql://...` — must be edited to
  `postgresql+asyncpg://...` and have `channel_binding`/`sslmode` params
  dropped (asyncpg doesn't parse them) before it works here.
- Prefer the synthetic test family for ad-hoc testing:
  `family_id=00000000-0000-0000-0000-000000000001`,
  `user_id=00000000-0000-0000-0000-000000000002` (mint a JWT with
  `issue_session_token`) — keeps scratch data separate from the copied
  real-looking family.
- The pytest suite is safe to run against either DB — every test runs
  inside one outer transaction rolled back at teardown
  (`tests/conftest.py`, `join_transaction_mode="create_savepoint"`).

Every worktree needs its own `backend/.env`/`frontend/.env.local`
(gitignored) — copy from `.env.example` or another working worktree.

## Lessons learned (don't reintroduce these)

- **Client store seeding**: `home/layout.tsx` starts the `/home` fetch
  un-awaited and passes the promise to `FamilyProvider`, which reads it
  via `use()` inside its own `<Suspense>`. Awaiting it in the layout body
  reintroduces the navigation-blocking trap (a layout doing an uncached
  fetch blocks every route beneath it; `loading.tsx` can't cover a
  layout, only `page.js`/nested layouts). `requireSession()` (cookie
  only) is fine directly in the layout body.
- React streaming leaves a `display:none` duplicate of a resolved
  `<Suspense>` subtree during hydration — a Playwright locator can
  transiently match two copies. Not a bug; scope locators to
  `visible=true`/`.first()`.
- **Optimistic rollbacks must be inverse patches, not snapshot
  restores** — two concurrent optimistic writes each snapshotting
  pre-write state will clobber each other on rollback if one fails.
  `applyKidBalanceDelta(id, +d)` rolling back as `(id, -d)` composes
  correctly. Currency change is the one deliberate snapshot-restore
  (big, human-paced, not realistically concurrent).
- `sqlalchemy.Enum(SomePyEnum)` binds by `.name` not `.value` by
  default — always pass `values_callable=lambda e: [m.value for m in e]`
  or asyncpg rejects writes (psycopg2 is more lenient, so this survives
  review until a real driver is hit).
- `func.case(...)` is wrong — `case()` is a standalone construct
  (`from sqlalchemy import case`), not under `func`.
- FastAPI dependency chains (`Depends(get_kid)` etc.) autobegin a
  transaction before the route body runs — a shared `transaction()`
  helper needs a SAVEPOINT (`begin_nested()`) for the already-in-progress
  case, not a skip-wrapping no-op (see `app/core/db.py`).
- Neon's pooled endpoint + `pool_pre_ping=True` roughly doubles latency
  (extra round-trip per request) — use `pool_recycle` instead.
- Global rarely-changing reference data (price/FX cache) should be
  cached in-process (`investing_service.load_price_context`), cleared on
  scheduler refresh + a TTL safety net. **Any new module-level cache
  must also be cleared in the `db_session` pytest fixture** or tests
  leak state through the shared process.
- Pydantic `Decimal` fields serialize as JSON strings, not numbers —
  frontend `lib/types.ts` reflects this deliberately.
- A DB column with no per-row currency (e.g. `debt_transactions.amount`)
  is implicitly "whatever the family's currency is right now" — changing
  currency without a conversion adjustment row silently corrupts every
  existing amount's meaning.
- Adding a nullable column new code assumes is "always set" crashes on
  every pre-migration row — backfill in the same/a follow-up migration,
  or degrade gracefully on NULL, ideally both.
- **Windows dev-server ghost-port bug, recurs across sessions**: a
  killed process can survive `Stop-Process`/`taskkill` reporting success
  while still actually answering requests — `netstat`/
  `Get-NetTCPConnection` shows a PID bound to a port that
  `Get-Process`/`Get-CimInstance` can't resolve, and it silently serves
  *stale* code, sometimes alongside a second, genuinely-fresh listener
  on the exact same port (whichever one answers is nondeterministic).
  Don't trust a clean restart log — `curl` a field/endpoint only the new
  code has. Don't waste time trying to kill the ghost; move the whole
  stack to a new port (update `.env.local` **and** restart the frontend
  process — Next only reads `.env.local` at process start) and move on.
  Treat "running server disagrees with code on disk" as this bug by
  default on this project.
- Always run `uvicorn` with `--reload` locally — without it, a `git
  merge` that changes backend files can leave the server answering with
  the pre-merge shape, which looks exactly like a real frontend bug.
  Even *with* `--reload`, don't assume every edited file was picked up —
  WatchFiles has logged only one reload for two near-simultaneous edits;
  if behavior doesn't match a change, kill and restart fresh.
- To screenshot a page behind `requireSession()` without real Google
  OAuth: mint a backend JWT (`issue_session_token`) + a matching Auth.js
  v5 session cookie via `next-auth/jwt`'s `encode({token, secret:
  AUTH_SECRET, salt: "authjs.session-token"})` (salt must be the literal
  cookie name), set as a Playwright context cookie before `page.goto`.
  Run the encode script from inside `frontend/` (needs its
  `node_modules`) with real Windows-style paths, and make sure frontend/
  backend ports match `CORS_ORIGINS` or every fetch fails as an
  unhelpful CORS rejection.
- A fire-and-forget `asyncio.create_task(...)` with no held reference
  can be garbage-collected mid-flight (documented asyncio footgun) —
  keep a module-level `set` of in-flight tasks, drop via
  `task.add_done_callback(the_set.discard)`.
- Postgres raises on an oversized `VARCHAR(n)` insert, it does not
  truncate — use `Text` for server-generated strings of uncontrolled
  length (an exception `repr()`, a raw request path); reserve capped
  `String` for already-validated fields.
- A module-level asyncpg pool (`app/core/db.py`'s `engine`) is not
  event-loop-aware; pytest-asyncio gives each test its own loop. A
  connection pooled via a direct `SessionLocal()` call in one test can
  get handed to a later test's different loop and crash with `RuntimeError:
  Event loop is closed`. Any test file where 2+ tests touch
  `SessionLocal`/`engine` directly needs an autouse fixture disposing the
  pool before/after each test (see `tests/test_scheduler.py`).
- `AsyncSession` can't be used concurrently — `asyncio.gather`-ing
  queries within one request needs a second connection, which breaks
  `tests/conftest.py`'s uncommitted-outer-transaction isolation. Reduce
  round-trip *count* (JOINs) instead of trying to parallelize.

## If you're picking up work in a parallel worktree

Likely one of several parallel Claude sessions, each its own `git
worktree` on its own `worker-N` branch, sharing this repo's history and
**the one Neon dev/test branch**.

- Each worktree has its own `backend/.env`/`frontend/.env.local` with a
  pre-assigned port pair (worker-1: 8011/3011, worker-2: 8012/3012,
  worker-3: last known 8100/3013 — **worker-3's port has drifted
  repeatedly chasing the ghost-port bug above; check `netstat`/
  `Get-NetTCPConnection`/`.env.local` for ground truth, don't trust this
  table**). A new worktree: pick the next free pair, install deps fresh
  (`.venv`/`node_modules` are gitignored, not shared).
- **`master` is the trunk and deploy branch** — merging to it redeploys
  production. Coordinate before merging anything touching what another
  worker is also mid-way through, **especially migrations**: check
  `alembic/versions/` for the latest number, but that's not sufficient —
  another worktree's *uncommitted* migration may already be applied
  against the shared DB. Run `alembic current` against the shared DB (or
  message the other session via `ListAgents`/`SendMessage`) before
  trusting a number is free. This has collided for real, more than once
  (migrations 0005, 0010 each independently claimed by two sessions) —
  resolution pattern: confirm what's actually applied vs. in-flight with
  the other session, renumber yours after theirs, temporarily copy their
  migration file(s) in to resolve the alembic chain locally, delete the
  copies once done, and know theirs must land in `master` before yours
  can merge cleanly.
- Don't assume you're the only session running — unexpected DB state
  (extra migration, test data) is probably another worker, check `git
  log`/recent migrations before assuming a bug.
- Pull `master` periodically to avoid a large end-of-session conflict.
- No separate `dev`/staging branch below `master` — deliberate, project
  is small enough not to need it.
- Before calling anything done: backend test suite (`cd backend &&
  pytest`), frontend `build && lint`, and actually look at any touched
  screen (Playwright or the real dev server) — this project has
  repeatedly found bugs static review alone missed.
- Update this file's status section when you finish a session of
  meaningful work.
