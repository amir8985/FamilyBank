# FamilyBank — Handoff / Orientation

Read this first. `FamilyBank_spec.md` and `FamilyBank_architecture.md` are
the product/architecture source of truth; `design_handoff_familybank/`
has the visual design. This file is session-to-session state: what's
built, what's verified, what's not done, and the non-obvious lessons
learned while building it — read it before starting new work, and update
it when you finish a session of meaningful work (especially if you hit
and fixed a real bug — the "Lessons learned" section exists so the next
session doesn't reintroduce it).

## Talking to the user

The user does not read most of a long response, especially not the
opening — skims are the default, not the exception. So: end every
response (not just this file's own updates) with a short, plain-language
summary of what actually matters — what changed, what's blocked, what
needs a decision from them, what to do next. Put it last, after the
detailed work, not only at the top. Don't rely on them having read the
play-by-play above it.

## What this is

Parents track allowance/debt owed to their kids; kids "invest" that
virtual balance in real stocks/indices at real market prices. No real
broker, no real money movement — see spec section 0 for the framing that
has to stay sharp on every screen.

```
backend/    FastAPI + SQLAlchemy + Postgres (Neon) — see backend/README.md
frontend/   Next.js 16 (App Router) + Tailwind v4 — see frontend/README.md
```

## Status as of 2026-09-07

**Instant UX: client-side data store + optimistic writes (frontend
v0.7.0, backend `prices_as_of` field). The app no longer freezes on a
slow backend — navigation between cached screens is instant and writes
reflect immediately, independent of the still-pending server region
move.** Motivated directly by the user: "even if the server takes time,
why can't we degrade the experience — when I deduct money I already have
all the data, show it done and save in the background; and Settings
should just open while it thinks." Both were true problems in how the
frontend was built:

- **Every `/home/*` page was a Server Component doing a blocking
  `await api.get(...)` with `cache: "no-store"`.** Navigating to Settings
  waited for the Next server to round-trip the backend (→ Neon) before
  sending any HTML. Nothing was cached client-side, so Home → Settings
  re-fetched `kids` + `base_currency` the user had *just* loaded. And
  `GET /family/settings` on the Settings page was **100% redundant** —
  it only used `base_currency`, already in the `/home` response
  (`onboarding_completed`, the only other field, is used solely by the
  layout gate). Same redundant `/family/settings` call was also in the
  kid-portfolio and buy pages.
- **Writes did `await api.post(...)` then `router.refresh()`** — a
  second full server round-trip — with the button stuck on
  "Confirming…" the whole time before any number moved. `debt-sheet`
  already computed the new balance locally and threw it away.

What shipped (hand-rolled — no new runtime dependency; the project keeps
to next/react/next-auth):

- **`src/lib/family-store.tsx` — `FamilyProvider` / `useFamily()`.**
  Holds the whole `/home` payload client-side for the session. Seeded
  **once** from a server-started, un-awaited promise passed from
  `home/layout.tsx` and read with React's `use()` inside the provider's
  own `<Suspense>` (the officially documented "use within a Context
  Provider" pattern —
  `node_modules/next/dist/docs/.../guides/single-page-applications.md`).
  The layout keeps the provider mounted across every in-segment
  navigation, so it suspends exactly once; every navigation after reads
  the store synchronously. Exposes `refreshHome()` (deduped background
  reconcile) and inverse-patch optimistic mutators
  (`applyKidBalanceDelta`, `addKidOptimistic`, `removeKidOptimistic`,
  `applyCurrencyOptimistic`) that each return a `rollback()` that
  composes safely with other in-flight optimistic writes.
- **`src/lib/use-cached-resource.ts`** — a tiny stale-while-revalidate
  cache (module-level `Map` + pub/sub) for the per-kid detail data that
  isn't in `/home` (portfolio, catalog, asset detail, debt/investment
  history). Serves last value instantly + revalidates in the
  background; `invalidateResource(keyOrPrefix)` after a write.
  Catalog/asset TTL ~10 min (prices only move ~5x/day — see
  `prices_as_of` below), portfolio ~15 s serve-stale-first.
- **`src/components/ui/toast.tsx`** — `ToastProvider` / `useToast()`.
  Optimistic writes close their sheet immediately, so a later failure
  ("Couldn't update Maya's balance — it's been restored.") has no inline
  spot; it surfaces as an auto-dismissing toast instead.
- **Screens now instant from the store:** Home + Settings read
  `useFamily()`, zero network on navigation (**Settings went from 2
  backend calls to 0**). Kid portfolio / buy / history pages are Client
  Components that render their header/name/cash **instantly** from the
  `/home` kid summary and stream the detail in via `useCachedResource`
  with section-level skeletons. All redundant `/family/settings` calls
  deleted (currency comes from the store).
- **Optimistic writes:** add/deduct money, add/remove kid, sell, and
  currency change all apply locally + close immediately, POST in the
  background, `refreshHome()` to reconcile, and toast + `rollback()` on
  failure. Buy keeps its "Buying…" button (it has a real server quote
  and is a deliberate action) but now invalidates the portfolio cache +
  `refreshHome()` instead of `router.refresh()`, so arriving at the
  portfolio screen is instant with fresh holdings streaming in.
- **Auth guard moved fully into `home/layout.tsx`** (`await
  requireSession()` in the body — it only reads/verifies the session
  cookie, no network, sub-ms block) since the pages below are now
  Client Components that can't call it themselves. The
  onboarding-completed check + the `/home` seed stay in their own
  `<Suspense>` boundaries (both are real backend calls — the
  navigation-blocking trap). `public.spec.ts`'s unauthenticated-redirect
  tests still pass.
- **Backend: `prices_as_of` (nullable datetime) added to `/home` and
  `/portfolio` responses** — the max `PriceCache.updated_at`, computed
  in Python from the already-loaded `PriceContext.prices` (no extra
  query; new `PriceContext.prices_as_of` property). It's the timestamp
  the user correctly pointed out "should already be there" (the
  scheduler stamps every price row the same time per ~5h refresh — see
  `jobs.last_refresh_at`). Lets the client cache price-derived screens
  with confidence. `/catalog` already exposed per-asset
  `price_updated_at`.
- **Verified for real:** 82 backend tests pass; frontend
  `build`/`lint` clean; drove it with Playwright against a minted
  NextAuth cookie + the synthetic test family (Maya/Noah seeded with a
  balance + a QQQ holding) — confirmed Home→Settings makes **zero**
  backend requests, deduct closes the sheet and moves the balance
  instantly, a forced-500 deduct rolls back + toasts, optimistic
  add/remove kid reconciles temp→real row, buy/currency-change/history
  all work with no console errors, and bad-kid-id / bad-symbol still hit
  the error boundary / not-found page.
- **Known cosmetic artifact, not a bug:** React streaming leaves a
  `display:none` duplicate of the resolved Suspense subtree in the DOM
  briefly during hydration (so `getByText` in a test can transiently
  match two copies, one hidden). Cleaned up once hydration completes;
  the user never sees it. Scope Playwright locators to `visible=true`.
- **Trade-offs accepted:** optimistic values can briefly snap back on a
  server rejection (rare — mitigated by toast + reconcile); the client
  cache can show data a few seconds stale until background revalidation
  (fine — prices move every 5h, balances reconcile within one
  `/home` refresh per write); the first hard load of any `/home/*` URL
  still needs one `/home` round-trip to seed the store (same wait as
  the old `loading.tsx`), every navigation after is instant.

**Production-slowness root cause found: it's per-query network latency
to Neon, multiplied by however many queries an endpoint runs
sequentially — not a missing index or a single bad query.** Started
from the request_logs data the 2026-09-06 logging feature collects.
Every query in production — including a trivial single-row
primary-key lookup with an index (`SELECT ... FROM kids WHERE id = $1`)
— has a floor of ~300-450ms, and this floor is nearly identical
regardless of the query's actual complexity (a plain PK lookup and a
multi-column INSERT cost about the same). That's the signature of
network round-trip time dominating over query execution, not query
cost — almost certainly Render's backend instance and the Neon project
not being in the same region (confirmed by the user; not yet changed —
see "Architecture review for scale" below, "Not yet done (2026-09-07)").
Since every endpoint in this codebase issues its
DB queries sequentially (each one `await`ed before the next starts),
this floor multiplies directly: `/buy` (9 queries) cost ~2.7s in DB
time alone, `/home` (4 queries) ~2-3.5s, matching exactly what users
reported ("every click takes a few seconds").

**Why this couldn't be fixed by parallelizing queries within a
request, and what was done instead.** The obvious fix — run
independent queries concurrently via `asyncio.gather` — turns out to
be unsafe here: SQLAlchemy's `AsyncSession` is documented as not safe
for concurrent use from multiple coroutines on one instance (one
connection can only run one statement at a time). True parallelism
would need each concurrent branch to open its *own* session/connection
— but `tests/conftest.py`'s test-isolation strategy runs every test
inside one outer transaction that's never committed
(`join_transaction_mode="create_savepoint"`, rolled back at teardown —
see its own docstring), so a second, independently-opened connection
inside the same request literally cannot see a test's uncommitted
fixture rows (Postgres transaction isolation). Opening extra
connections for concurrency would have silently broken every test that
seeds data and then hits an endpoint using it. Given that, the fix
actually applied was **reducing the number of round-trips instead of
parallelizing them**, which doesn't have this problem (still one
connection, same session, just fewer separate `SELECT`s):
- `investing_service.get_asset_detail` (backs `GET /catalog/{symbol}`)
  was doing 3 of its own raw per-symbol queries (`session.get`
  ×2 + `fx_service.convert`) instead of reusing
  `load_price_context`'s shared, scheduler-refreshed, in-process cache
  like every other read path in this module already does — a genuine
  miss from the batching pass described in the module's own docstring.
  Fixed to route through the cache like the rest; costs ~0 extra
  queries on a warm cache instead of always 3.
- `load_price_context` itself did 2 separate `SELECT *`s (catalog,
  then price_cache) on a cache miss — now one `LEFT JOIN` (outer, since
  a symbol can exist in the catalog with no price row yet). This runs
  on every read endpoint's cold-cache path (TTL expiry or right after a
  scheduler refresh clears it), so it's on the critical path of nearly
  everything.
- Net effect: fewer round-trips per request, but each remaining
  round-trip still pays the same ~300-450ms floor — **this is a real
  improvement, not a fix for the underlying cause.** The actual fix is
  the region mismatch (see "Architecture review for scale" below,
  "Not yet done (2026-09-07)"); no amount of query reduction inside one
  request substitutes for that.

**Follow-up, same day: traced two specific screens (Settings, the
Add/Deduct sheet) query-by-query at the user's request, because "1-5
queries taking multiple seconds" didn't sound reasonable on its own —
correctly, it doesn't fully add up, and tracing it exactly surfaced
both a real remaining bug and a real gap in what the logging can prove.**
- `GET /family/settings` issues exactly **one** query (`get_family`'s
  `db.get(Family, id)` — the route body itself does nothing else). Yet
  production logs showed this same request taking up to 1842ms total
  while `db_time_ms` was only ~426ms — over 1400ms unaccounted for by
  the only query that ran. `request_logging.py`'s own comment already
  named the candidates: "Python processing, external calls, or waiting
  for a connection to free up." There's no external call and trivial
  Python here, which points squarely at **connection acquisition** —
  either waiting for a pooled connection to free up, or paying a brand
  new physical connection's full TCP+TLS+Postgres-auth handshake (see
  the `"db: established a new physical connection"` log lines, which
  fire more often than "once at startup" in the captured window) —
  and that cost is invisible to `db_time_ms`, which only wraps
  `before_cursor_execute`→`after_cursor_execute` (i.e., starts timing
  *after* a connection is already in hand).
- `POST /kids/{id}/debt` (the Add/Deduct sheet) issues exactly **5**:
  `get_kid` (tenant-scoped Kid lookup — necessary), `get_family`
  (needed for `family.base_currency` in the response — Kid has no
  currency of its own, so this isn't avoidable without denormalizing
  currency onto Kid, which has its own well-documented trap — see
  "Lessons learned"), `get_balance` for `balance_before`, the
  `INSERT` itself, and — this was the actual bug —**a second, fully
  redundant `get_balance` call for `new_balance`**, re-running the same
  `SUM(...)` over the kid's whole ledger a second time when the route
  already knows exactly what it just inserted. Fixed: `new_balance` is
  now computed as `balance_before ± body.amount` in Python
  (`routes_debt.py`) instead of re-querying — cuts this endpoint from 5
  queries to 4, specifically removing one of the two ~1.1s `SUM`
  aggregates seen in production. Also strictly more correct, not just
  faster: the old code's second `SUM` could reflect an unrelated write
  landing between the commit and that query, silently mislabeling the
  response's "new balance" with a number this request didn't actually
  produce.
- **The user then pushed on `get_kid` + `get_family` specifically: two
  separate point-lookups per request, when the route already knows
  both ids and both are simple, related rows — asked directly why this
  couldn't be one query.** It could, and now is:
  `app/api/deps.get_kid_and_family` (new) replaces the pair with a
  single `SELECT ... FROM kids JOIN families ...` — one round-trip
  instead of two, same tenant-isolation check as `get_kid` (still
  explicit, not just implied by the JOIN condition — a kid_id from
  another family still 404s;
  `tests/test_api_family_isolation.py` still passes unchanged).
  Swapped in everywhere both were used together: `routes_debt.py` (both
  routes) and `routes_investing.py` (`get_portfolio`, `quote_purchase`,
  `buy`, `sell`) — **`POST /kids/{id}/debt` is now 3 queries, down from
  the original 5**; `/buy` and the others each drop one query too.
  `get_kid`/`get_family` on their own are unchanged and still used
  where a route only needs one (e.g. `list_investment_transactions`
  only needs the kid).
- **Turned the connection-acquisition hypothesis into something the
  next round of production logs can actually prove, instead of leaving
  it as a guess.** Added `time_to_first_query_ms` to the structured
  stdout log line (`app/core/query_timing.py` +
  `app/core/request_logging.py`, stdout-only like `db_query_count`/
  `db_time_ms` — not persisted) — the elapsed time from request start
  to the *first* query's `before_cursor_execute`, which is exactly
  where a pool checkout or a fresh connection's handshake would show
  up and nowhere else currently does. On `GET /family/settings`, a
  large `time_to_first_query_ms` relative to `db_time_ms` (e.g. the
  1400ms/426ms case above) would confirm the connection-acquisition
  theory directly; a small one would mean the gap is something else and
  this theory is wrong. **Next session: once this is live, check that
  field on a few of the slowest single-query requests before assuming
  anything further about the cause.**
- Two remaining necessary-but-real costs, left as-is because they're
  inherent to the design, not bugs: (1) `get_kid`+`get_family` are two
  separate point-lookups per request that touch anything kid-scoped —
  this is the tenant-isolation enforcement point
  (`app/api/deps.py`, and the property `test_api_family_isolation.py`
  guards), not something to collapse away; (2) `get_balance` is a full
  `SUM` over a kid's ledger rather than a stored running total, by
  deliberate design (CLAUDE.md's "Architecture quick-reference": "never
  stored redundantly" — buy/sell writes stay consistent with the ledger
  specifically *because* nothing caches a derived balance). Both are
  small, single-purpose queries; at this app's data volumes neither
  should be inherently slow — if `time_to_first_query_ms` rules out
  connection overhead, `get_balance`'s `SUM` cost specifically (not
  just its round-trip) would be the next thing worth measuring for real
  row counts on the actual production kid, not guessed at.

**`request_logs` now has actual retention** (backend v1.5.0) — nothing
previously deleted from this table; at real traffic it would grow
forever, costing Neon storage and eventually slowing down the very
diagnostic queries it exists to enable.
`app/scheduler/jobs.cleanup_old_request_logs` prunes rows older than
`settings.request_log_retention_days` (default 30), piggybacked onto
the existing price/FX refresh cadence (`run_refresh`) rather than
needing its own schedule — a plain `DELETE` against the already-indexed
`created_at` column is cheap enough not to warrant one.

**`POST /internal/client-metrics` is now rate-limited per IP**
(`app/core/rate_limit.py`, 30 req/60s, in-memory) — this was the one
endpoint with no auth requirement and no shared secret (CLAUDE.md had
flagged it as a known gap), genuinely reachable by anyone; a flood
would grow `request_logs` and cost real Neon compute for nothing. Over
the limit, the endpoint still returns 200 (this is best-effort
telemetry — the frontend beacon fires-and-forgets and never checks the
response) but silently drops the entry instead of logging it. Comes
with the same module-level-cache test-isolation trap the price-context
cache already had (see "Lessons learned") — httpx's `ASGITransport`
gives every test request the same fake client address by default, so
`clear_rate_limit_state()` had to be added to `db_session`'s
setup/teardown alongside `clear_price_context_cache()`, or one test
hitting the limit would silently poison every later test's ability to
call this endpoint. **Requires `render.yaml`'s `startCommand` to pass
`--proxy-headers`** (added) — without it, `request.client.host` always
sees Render's own edge proxy, not the real visitor, since Render
always sits in front; safe to trust here specifically because Render's
proxy is the only thing that can open a direct connection to this
process. In-memory and per-process — if this backend ever runs as more
than one instance, each enforces the cap independently rather than
sharing one global count; revisit with a shared store (Redis) if that
ever becomes the deployment shape.

**Frontend: every navigation under `/home/*` now shows instantly, with
a real loading state or a friendly error screen, instead of freezing
with no feedback (frontend v0.6.0).** Motivated by a real observation:
if the backend is slow (see above) or unreachable, a parent tapping
Settings saw nothing happen at all — no URL change, no spinner, no
error — until the request either resolved or hung. Root cause: **zero
`loading.tsx`/`error.tsx` files existed anywhere in the app**, and
every page was a Server Component doing a blocking `await api.get(...)`
with `cache: "no-store"`, so a slow/dead backend blocked the entire
route transition.
- Added a `loading.tsx` (lightweight skeleton, `components/ui/skeleton.tsx`)
  to every route segment under `/home` and `/onboarding`, and an
  `error.tsx` (`components/ui/error-state.tsx` — "Something went
  wrong" + Try again/Back to home) at `/home`, `/onboarding`, and the
  root, so a thrown `ApiError` (backend down, 5xx, or an uncaught 404
  like a since-deleted kid_id) renders a real screen instead of a crash.
- **The harder part, and the one that actually makes any of the above
  take effect: `home/layout.tsx` had to be restructured.** It did its
  own blocking fetch (`/family/settings`, to redirect to `/onboarding`
  if incomplete) directly in the layout body. Per this exact Next.js
  version's own docs
  (`node_modules/next/dist/docs/.../file-conventions/layout.md`,
  "Interaction with loading.js" — **read this before touching
  layout/page fetch patterns again; this project's `AGENTS.md` warns
  this Next.js version's conventions can differ from training data,
  and this is a concrete example of that**): a layout that does an
  uncached fetch **blocks navigation for every route beneath it**, and
  none of that segment's `loading.tsx` files can ever show for it —
  `loading.tsx` only wraps `page.js` and nested layouts, never the
  segment's own `layout.js`. Fixed by extracting the fetch+redirect
  into a small `OnboardingGate` async component, Suspense-wrapped
  (`fallback={null}`) inside `HomeLayout`, with `{children}` rendered
  as a sibling outside that boundary — exactly the pattern the docs
  show for this. **Trade-off accepted deliberately:** a user who lands
  on a `/home/*` URL before completing onboarding could now see a brief
  flash of real page content before the redirect fires, instead of
  never seeing it — not a security issue (the backend still enforces
  real authorization on every call regardless of what this gate does),
  just a rare, cosmetic edge case traded for instant navigation on
  every normal request.
- Verified for real (not just build+lint): minted a valid NextAuth
  session cookie directly (via `@auth/core/jwt`'s `encode()`, the same
  `AUTH_SECRET` from `.env.local`, salt = the cookie name) against the
  synthetic test family from CLAUDE.md's dev/test-DB section, drove it
  with Playwright — normal navigation to `/home`/`/home/settings`
  renders real data with zero console errors, and navigating to a
  well-formed but nonexistent kid_id (a stand-in for "the backend
  failed" — same code path, `api.get` throwing an uncaught `ApiError`)
  correctly rendered the new error screen with a working Try again
  button instead of a blank/crashed page. Didn't literally kill the
  local backend process for this — see "Lessons learned" for why.

**A real, pre-existing pytest bug found and fixed while adding the
`request_logs` cleanup test: `app.core.db.engine`'s connection pool is
not event-loop-aware, and pytest-asyncio gives every test function its
own event loop.** `app/core/db.py`'s module-level `SessionLocal`/`engine`
is a process-wide singleton (by design — it's the real engine used
outside of tests too). asyncpg connections are tied to the event loop
that created them; when a test pools a connection via a direct
`SessionLocal()` call (the pattern `tests/test_scheduler.py` already
used for `last_refresh_at`), that connection can get checked back out
to a *later* test's different loop and immediately blow up with
`RuntimeError: Event loop is closed` on first use — not a bug in
whichever test happens to draw it. Only `test_scheduler.py` touches
`SessionLocal` directly among test files, so it was invisible until a
second test in that file did the same thing (the new
`test_cleanup_old_request_logs_...` test). Fixed with an autouse
fixture scoped to that one file that disposes `engine`'s pool before
and after each test — see its docstring in `tests/test_scheduler.py`
if you add a test elsewhere that touches `SessionLocal`/`engine`
directly; the same trap applies there too.

**Architecture review for scale (thousands-tens of thousands of
users), requested directly — findings, and what's still open:**
- **Not yet done (2026-09-07) — region mismatch, the real fix for the
  slowness above:** the user confirmed Render and Neon are not in the
  same region; not yet changed (needs a dashboard decision — pick a
  Render region and/or a Neon project region that are actually close,
  possibly requiring a new service/project — not a code change). No
  amount of query-count reduction fully substitutes for this.
- **Single Render instance, single uvicorn process, no `--workers`.**
  Fine for today's traffic (this app is I/O-bound — one async event
  loop handles a lot of concurrent waiting-on-Neon requests) but it's a
  single point of failure with no redundancy, and any CPU-bound stretch
  (JWT verification, Pydantic validation, JSON serialization) serializes
  across every concurrent request in that one process. Revisit if/when
  traffic actually grows enough to matter — not done preemptively here.
- **The in-process scheduler (`app/scheduler/loop.py`) assumes exactly
  one long-running instance.** If this backend ever runs as more than
  one Render instance, each would run its own copy of the refresh loop
  independently — redundant Yahoo/FX API calls per instance, and no
  coordination writing the same `price_cache`/`fx_rates_cache` rows
  (upserts, so not *unsafe*, just wasteful and racy about which
  instance's data "wins"). Needs a real fix (leader election, or move
  to the external-cron `/internal/refresh` model the code already
  supports for serverless) before adding a second instance — don't add
  one without addressing this first.
- **Connection ceiling**: this process's pool is unconfigured
  (`pool_size`/`max_overflow` left at SQLAlchemy's defaults, 5+10=15),
  plus the request-logging middleware and the scheduler each open their
  own separate connections via `SessionLocal` outside the request pool.
  Fine for one instance at today's scale; Neon's free tier has its own
  connection ceiling that a second instance (or raising `pool_size`)
  could approach — check Neon's dashboard limits before scaling either
  dimension.
- **`request_logs` retention** — done this session (see above).
- **`/internal/client-metrics` abuse resistance** — done this session
  (rate limit, see above); still no auth/shared secret by design (a
  metric from a signed-out screen is still worth logging), so the rate
  limit is the only defense, not a full fix.
- **The free tiers themselves (Render + Neon) are not built for
  "thousands of users" regardless of any code-level fix** — cold
  starts, shared/throttled CPU, and hard connection/storage ceilings
  are platform limits, not something this codebase can optimize past.
  Getting to real scale needs a paid-tier decision from the user
  (cost), not more code changes — flagged, not resolved here.
- Did **not** find further N+1 query patterns beyond the two fixed
  above in this pass (checked `/home`, `/catalog`, `/catalog/{symbol}`,
  `/kids/{id}/portfolio`, `/kids/{id}/quote`, `/kids/{id}/buy`,
  `/kids/{id}/debt`) — the remaining per-endpoint query counts are
  already about as low as they can be within one session/connection.

## Status as of 2026-09-06

**Built and verified:** the full v1 flow — Google-only sign-in →
onboarding (currency + first kids) → home (balances, add/deduct) → kid
portfolio (holdings, since-purchase %, sell) → buy flow (units/amount
toggle with a live server-computed quote, snapped to a real tradable
step size) → per-kid history (general + investment-only, now currency-
and source-aware — see below) → settings (currency, kid management,
**real currency conversion with a warning dialog**). 74 backend tests
pass (`cd backend && pytest`), frontend `npm run build`/`npm run lint`
are clean.

**Request/performance logging + client-side timing beacon (built
2026-09-06, backend v1.3.0 / frontend v0.6.0).** Motivated by a real
report: production feels slow on some clicks, but it's not reproducible
locally — with zero request-level logging in place beforehand, there was
no way to tell whether that's Render's free-tier cold start (sleeps
after 15 min idle, 30-50s to wake), the DB, or something in app code.
This ships the diagnostic instrumentation, not a fix for the slowness
itself — see "How to actually find the problem" below for the next step.
- **`RequestLoggingMiddleware`** (`app/core/request_logging.py`) times
  every backend request, tags it with `user_id`/`family_id` decoded
  straight off the session JWT (no dependency on the route's own auth —
  works even for a request that 401s/404s), and both logs a structured
  JSON line to stdout (viewable in Render's log tail immediately, no new
  accounts needed) and writes a row to a new `request_logs` table
  (migration `0010`) so it's actually queryable/aggregable later — this
  doubles as the seed data for a future per-family/user activity
  dashboard (deliberately out of scope for this feature — see TODO.txt),
  which is why family/user id is captured now even though this feature
  only uses it for latency, not activity, analysis.
- **Deliberately a raw ASGI middleware, not `BaseHTTPMiddleware`** — the
  latter buffers the whole response through an in-memory stream per
  request, which is itself measurable overhead. Would have been ironic
  for a performance feature to make requests slower.
- **`POST /internal/client-metrics`**: the frontend's one shared
  `request()` function (`frontend/src/lib/api.ts`, used by every API call
  in the app) times each call — success or failure — and fires a
  non-blocking beacon here with the real HTTP method, path, duration, and
  status. This is what tells slow-client-or-network apart from
  slow-server for the *same* logical action, which server-side logging
  alone can never do. Auth is optional on this endpoint (a metric from a
  signed-out screen is still worth logging).
- **Persistence is fire-and-forget on both write paths**
  (`spawn_persist_request_log`) — a response must never block on the log
  INSERT itself, or the feature would add to the very latency it exists
  to diagnose. Tracked in a module-level set with a done-callback rather
  than a bare `asyncio.create_task(...)`, per asyncio's own documented
  warning that an unreferenced Task can be garbage-collected mid-flight.
- **`path`/`error` columns are `Text`, not a length-capped `String`** —
  Postgres raises on an oversized `VARCHAR(n)` insert rather than
  truncating, which is the one thing a *logging* write must never do
  (an unmatched/malformed raw URL, or an unhandled exception's `repr()`,
  can't be bounded in advance the way validated user input can).
- **DB persistence is disabled for the whole pytest suite**
  (`tests/conftest.py`'s autouse `_no_request_log_persistence`, toggled
  via `request_logging.set_persist_enabled`) — this middleware writes
  through its own connection (`SessionLocal`), not the request-scoped
  session the `client` fixture overrides, so left enabled it would insert
  a real, never-rolled-back row into the shared dev/test DB on every
  single request the test suite makes.
- **Known limitation, not addressed:** `/internal/client-metrics` has no
  auth requirement, rate limit, or shared secret (unlike `/internal/refresh`'s
  scheduler-secret header) — it's genuinely reachable by anyone on the
  internet, and an anonymous flood of POSTs would grow `request_logs` and
  cost real Neon storage/compute. Left as-is for now given this app's low
  profile (same risk-tolerance call as the currency-conversion race
  condition below), but worth knowing if abuse ever shows up in the data.
- **Real-world multi-worker migration collision, again:** this branch's
  migration also landed as `0010` while worker-3 (a parallel session, same
  machine) had independently reached `0010`/`0011` for an unrelated
  feature, already applied to the shared dev/test DB. Same root cause and
  resolution pattern as the `0005`-`0008` collision documented below —
  worker-3 had already reconstructed a placeholder `0010` file (see its
  own docstring) after discovering `alembic upgrade head` silently no-op'd
  against a revision id we'd both claimed; coordinated directly via
  `SendMessage` before pushing, worker-3 will delete their placeholder
  once this branch's real `0010_request_logs.py` is on `master`.

**How to actually find the production slowness, next** (the point of
this feature): once this is live, let it collect at least a day of real
traffic, then query `request_logs` directly — no dashboard needed yet:
```sql
SELECT path, source, count(*), avg(duration_ms),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95
FROM request_logs
WHERE created_at > now() - interval '2 days'
GROUP BY path, source ORDER BY p95 DESC;
```
Rule out the cheap explanation first — filter `duration_ms > 5000` and
check whether those rows cluster right after long gaps for the same
family (Render's free-tier cold start; no amount of logging fixes that,
only a paid tier or a keep-warm ping would). Then compare `source='client'`
vs `source='server'` for the same `path`: a big gap points at
network/cold-start, a small gap with both slow points at the backend
itself (likely DB/Neon, per the `pool_recycle` note below). If that
aggregation doesn't pinpoint it, the natural next step is sub-timing
(DB time vs. external-API time) inside specific slow endpoints — worth
doing once you know *which* ones, not before.

**UI polish: currency-symbol font fix, button/color consistency, touch
targets (built 2026-09-04, frontend-only, v0.5.0).** A parent testing on
Android saw ₪ rendering broken/heavy — Source Serif 4 (the serif font
used for every money numeral) has no real ₪ glyph, so it silently fell
back to a mismatched system serif. Fixed generically, not ₪-specifically:
- **New `formatMoneyParts`/`<Money>`** (`lib/format.ts`,
  `components/ui/money.tsx`) split a formatted amount around its
  currency symbol via `Intl...formatToParts`, so callers can render the
  symbol in `font-sans` while the numeral stays in the inherited serif —
  works for any currency, not just ILS. Swapped in at every call site
  actually rendered under `font-serif` (checked each one individually —
  most money displays in this app are plain sans-serif already and
  didn't need touching); the two standalone-symbol spots (buy/debt
  amount-input prefixes) just got a `font-sans` span directly, no
  component needed.
- **Deduct now reads as a distinct, red action** — new
  `--color-tint-negative` token, plus the balance-update sheet's
  Add/Deduct toggle (`SegmentedControl`'s `filled` variant) goes solid
  red when Deduct is active via a new per-option `activeClassName`
  override (previously both options showed emerald when selected,
  regardless of which one).
- **`--color-positive` changed from amber/brass to green** — inherited
  from the original design handoff's own token value, not a bug in this
  codebase, but the *only* place amber/brass was reserved for gains
  while red meant losses read as inconsistent once seen live (kid asked
  "why is Deducted the same green as everything else, and Added is
  yellow"). Affects every day-change %/since-purchase %/history-amount
  display that reads this token — all green now.
- **44px minimum touch target** (`min-h-11`) on every pill/filled/
  outlined button app-wide (not plain text links like "History").
- Home screen: "You owe" → "Total balance", wrapped in a
  bordered+shadowed card matching the kid cards below it.
- App version now shown at the bottom of Settings, read directly from
  `package.json` (`v0.5.0`) so it can't drift out of sync.
- **Known gap, not addressed:** phone/LAN dev testing with real Google
  sign-in doesn't work — Google's OAuth redirect-URI validation rejects
  a private LAN IP outright (this is separate from the "authorized
  redirect URI list" issue below; registering the LAN IP doesn't fix it
  because Google won't accept a non-localhost IP literal there at all).
  An HTTPS tunnel (ngrok et al.) registered with Google is the only
  workaround found; not set up this session.
- **If you add a new worktree/change the frontend dev port:** Google's
  OAuth client needs `http://localhost:<port>/api/auth/callback/google`
  added to its Authorized redirect URIs (Google Cloud Console →
  Credentials) or sign-in fails with "Access blocked" — only port 3000
  was registered originally. This is independent of the client's
  Testing/Published status (see the launch-compliance entry below) —
  it's a separate allowlist.

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

**Launch-compliance: privacy policy, terms of service, and consent
tracking (built 2026-09-03).** Two pre-launch requirements from spec 4.2
are done: a real `/privacy` and `/terms` page (Portugal named as
governing law/venue in the Terms — the app's operator's home
jurisdiction, chosen deliberately as a deterrent against nuisance
claims, not as a compliance guarantee — see the conversation this
shipped from if you need the reasoning again), and a consent gate in
front of Google sign-in. Key decisions:
- **Consent is a UI gate, not a piece of data threaded through the
  OAuth round-trip.** `sign-in-button.tsx`'s `SignInButton` opens a
  `BottomSheet` ("Before you continue") with a checkbox that must be
  checked before "Continue with Google" enables; only then does the
  existing `signIn("google", ...)` fire. This sidesteps needing to pass
  a consent flag through NextAuth's server-side `jwt` callback (which
  doesn't have clean access to client state across the Google redirect
  round-trip) — the button being disabled *is* the enforcement.
- **`users.consent_accepted_at`** (migration `0009`) is stamped once, in
  `routes_auth.py`, only when a brand-new user row is created — not on
  every sign-in. It's the audit-trail record of "this account was
  created under the consent-gated flow." **NULL means the account
  predates this feature, not that consent was declined** — it isn't
  backfilled for existing accounts, since there's nothing honest to
  backfill.
- **The Google OAuth client is now published** (Google Cloud
  Console → Audience → the app moved out of "Testing" mode) — the app
  only requests non-sensitive scopes (`openid email profile`), so this
  didn't require Google's manual verification review, just filling in
  Branding (app info + the two policy links) and publishing. Anyone with
  a Google account can now sign in, not just an explicit test-user
  allowlist.
- Shared layout between the two legal pages lives in
  `components/legal-page.tsx` (`LegalPage`/`LegalSection`) — write both
  pages through that rather than re-duplicating the nav/footer shell.
- **Real-world multi-worker collision, resolved along the way:** this
  branch's migration was originally also numbered `0005`, colliding with
  worker-3's in-flight (uncommitted-at-the-time) `0005`-`0008`. See the
  "If you're picking up work in a parallel worktree" section below for
  exactly how that got resolved — worth reading if you hit the same
  thing.

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
  its schema is current (migrations applied through 0009 as of this
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

- **The client family store (`src/lib/family-store.tsx`) is seeded from
  a server-started promise, NOT an `await` in the layout body.**
  `home/layout.tsx` does `const homePromise = api.get("/home", token)`
  (no `await`) and passes it to `<FamilyProvider>`, which reads it with
  React `use()` inside its *own* `<Suspense>`. Awaiting it in the layout
  body would re-introduce the exact navigation-blocking trap the whole
  feature exists to remove (a layout that does an uncached fetch blocks
  every route beneath it and no `loading.tsx` can cover it). The
  provider must keep its own `<Suspense>` — `use()` suspends and
  `home/loading.tsx` sits *below* the provider so can't catch it.
  `requireSession()` in the layout body is fine (cookie-only, no
  network) and is now the sole auth guard for the segment since the
  pages are Client Components.
- **React streaming leaves a `display:none` duplicate of a resolved
  `<Suspense>` subtree in the DOM during hydration.** A Playwright
  `getByText("Maya")` can transiently match two copies (one hidden) and
  fail strict-mode. Not a bug — it's how React delivers streamed
  Suspense content (hidden div, then moved into place), gone once
  hydration finishes. Scope test locators to `visible=true` /
  `.first()` and `waitForLoadState("networkidle")`; the user never sees
  it.
- **Optimistic rollbacks must be inverse patches, not snapshot
  restores** (see `family-store.tsx`'s mutators). Two rapid optimistic
  writes (deduct on two kids) each capture a pre-write snapshot; if one
  fails and restores its snapshot it clobbers the other's change.
  `applyKidBalanceDelta(id, +d)` rolling back as `applyKidBalanceDelta(id, -d)`
  composes correctly. Currency change is the one snapshot-restore
  rollback (big, human-paced, not realistically concurrent).
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
- **Always start `uvicorn` locally with `--reload`.** Started it once
  without the flag, then did two `git merge`s that changed backend
  files (a full currency-history rewrite) — the running server kept
  answering with the pre-merge response shape, which surfaced as a real
  runtime crash on the frontend (`Cannot read properties of undefined
  (reading 'toFixed')`, since a field the new frontend code expected was
  simply missing from the old server's response). Looked exactly like a
  genuine bug for several minutes before realizing the server just
  hadn't restarted. `--reload` watches file changes (including ones from
  git) and avoids this entirely.
- **Even *with* `--reload`, don't assume every edited file actually got
  picked up.** Editing two files in quick succession, WatchFiles logged
  only one "detected changes in ... Reloading" line and never restarted
  for the other — the server kept answering with the pre-edit behavior
  for that file indefinitely. Worse, `taskkill` on the resulting stale
  PID reported `SUCCESS` while `netstat` kept showing it bound and still
  serving requests — the same "kill reports success but it's still
  alive" symptom as the orphaned-server entry above, but this time with
  `--reload` on the whole time. If a running dev server's behavior
  doesn't match a change you just made, don't trust reload logs — kill
  it and start fresh (or move ports, per the entry above, if killing
  doesn't stick either). This didn't affect anything shipped — the real
  verification was the pytest suite, which imports the actual module
  fresh each run and isn't subject to this class of staleness at all.
- **A fire-and-forget `asyncio.create_task(...)` with no reference held
  is a documented footgun** — asyncio's own docs warn the Task can be
  garbage-collected mid-execution if nothing else references it. Keep a
  module-level `set` of in-flight tasks and drop each one via
  `task.add_done_callback(the_set.discard)` instead of calling
  `create_task` bare (see `request_logging.spawn_persist_request_log`).
- **Postgres raises on an oversized `VARCHAR(n)` insert — it does not
  silently truncate.** A column meant to hold a server-generated string
  you don't fully control the length of (an exception's `repr()`, a raw
  unmatched request path) needs `Text`, not a capped `String`, or a rare
  edge case turns a logging write into a crash (caught here since it's
  wrapped in try/except, but the row is silently lost instead of stored).
  Reserve length-capped columns for fields already validated at a
  boundary (Pydantic, a fixed enum) where the cap can never be exceeded.
- **A module-level asyncpg connection pool (`app/core/db.py`'s
  `engine`/`SessionLocal`) is not event-loop-aware, and pytest-asyncio
  gives every test function its own event loop by default.** A
  connection pooled during one test (via a direct `SessionLocal()` call
  — see `tests/test_scheduler.py`) can get handed back out to a
  *later* test's different loop and crash with `RuntimeError: Event
  loop is closed` on its very first use there — not a bug in whichever
  test happens to draw the stale connection. Only bites a test file
  once *two or more* of its tests touch `SessionLocal`/`engine`
  directly (the normal `db_session`/`client` fixtures use their own
  separate per-test engine and don't have this problem). Fix: an
  autouse fixture in that file that disposes `engine`'s pool before and
  after each test (see `tests/test_scheduler.py`'s
  `_dispose_module_engine_pool`) — forces a fresh, current-loop
  connection instead of reusing a stale one, regardless of test order.
- **`AsyncSession` cannot be used concurrently** (SQLAlchemy's own
  documented constraint — one connection runs one statement at a time),
  so `asyncio.gather`-ing independent queries within one request isn't
  a safe way to cut latency here without opening a second
  session/connection per concurrent branch. That in turn conflicts with
  this codebase's test-isolation strategy: `tests/conftest.py` runs
  every test inside one *uncommitted* outer transaction
  (`join_transaction_mode="create_savepoint"`), so a second,
  independently-opened connection mid-request literally can't see a
  test's seeded-but-uncommitted fixture rows (plain Postgres
  transaction isolation — nothing SQLAlchemy-specific). If you want to
  genuinely parallelize DB reads within a request, the number of
  round-trips is the lever that's actually safe to pull (fewer,
  broader queries — e.g. a `JOIN` instead of two `SELECT`s), not
  concurrency on the existing session.

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
  This isn't hypothetical — it happened on 2026-09-03: worker-3 had
  0005-0008 committed locally (not yet in `master`) and already applied
  to the shared dev/test branch, while worker-2 had independently
  written its own 0005. Resolution: message the other session directly
  (`ListAgents`/`SendMessage` — they're interactive Claude sessions on
  the same machine, not black boxes) to confirm what's actually applied
  vs. still in flight, rename your migration to sit after theirs
  (down_revision pointing at their real head), then to actually run
  `alembic upgrade head` locally you need their migration *files*
  physically present (Alembic needs the whole chain on disk to resolve
  revisions, even though it won't re-run already-applied ones) — copy
  them in from their worktree, run your migration, then delete the
  copies again so your branch's diff stays just your own file. Their
  migrations still need to land in `master` before yours can merge
  cleanly (down_revision references a revision `master` doesn't have
  yet).
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
