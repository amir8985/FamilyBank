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

## Status as of 2026-09-07 — savings plans (backend v1.7.0 / frontend v0.8.0)

**Built, tested, and verified live on branch `savings-plans` (cut from
`9a06555`, which is `origin/master` — the stock-boost feature is already
on master). NOT yet pushed / merged — that's gated on explicit user
confirmation per this project's rules.**

What it is: parents define **savings plans** a kid can move cash into.
One unified model — a plan is *flexible* (`lock_months == 0`, withdraw
any time) or *locked* (`lock_months > 0`, no withdrawal until it
matures, then it keeps compounding at the same rate until withdrawn).
Rate is a monthly percentage, compounded daily on read.

- **Deliberately one model, not two** (this was a mid-design call by the
  user): the parent only *creates and deletes* plans. Every
  `SavingsDeposit` **snapshots** its plan's `plan_name` / `monthly_rate`
  / `lock_months` at deposit time, so editing or deleting the parent's
  `SavingsPlan` never changes money already in it (`plan_id` is
  `ON DELETE SET NULL`; the snapshot columns are what actually drive
  display + math). The settings UI warns the parent with the
  open-deposit count before a delete.
- **`savings_service` is stateless like `boost_service`** — a deposit's
  value is `principal * (1 + rate/100) ** (elapsed_days / 30.4375)`,
  recomputed every read, no accrued-interest column, no cron job. Only
  ever grows (no down-ticks), so it's a plain compounding curve, not a
  tick walk. `DAYS_PER_MONTH = 30.4375` (= 365.25/12, matches
  `boost_service`'s `HOURS_PER_MONTH`).
- **Deposits are whole-only** (user's call): a withdrawal closes the
  entire deposit and pays principal + accrued interest back to the cash
  ledger via a `debt_transactions` row with the new **`is_savings`**
  flag (migration `0012`, `server_default false` — same safe pattern as
  `is_investment`; history shows "Moved to savings" / "Savings payout").
- **Migration `0012`** (`0011 → 0012`; shared dev DB is on it): adds
  `savings_plans`, `savings_deposits`, `debt_transactions.is_savings`.
  Checked `alembic current` against the shared DB + every sibling
  worktree's `versions/` before taking `0012` — nothing else had it in
  flight.
- **Routes** (`routes_savings.py`, new): `GET/POST /family/savings-plans`,
  `PATCH/DELETE /family/savings-plans/{id}`; `GET /kids/{id}/savings`,
  `POST /kids/{id}/savings/deposit`, `POST /kids/{id}/savings/{id}/withdraw`,
  `GET /kids/{id}/savings/{id}`. `PortfolioOut` gained `savings_value`.
- **Frontend**: Settings page — Kids list moved **below** the "Advanced
  investing & savings" link. Hub savings settings — **see the "Second
  round" bullet below for the current shape** (this first pass had a
  single `/savings-plans` screen; it was split into flexible/locked +
  presets before commit). Live **compounded** "≈ X%/year" hint —
  `annualFromMonthly` in `lib/format.ts` mirrors
  `savings_service.annual_rate` (2%/mo shows ~26.8%/yr, not 24%). Kid
  portfolio: header → "{Name}'s Investments &
  Savings"; segments **Portfolio / Invest / Save**; Portfolio tab shows
  a **Savings** section above **Investments**; "Sell everything" →
  **"Sell all investments for $X"** (+ its `confirm()` now says savings
  aren't affected). New **Save** tab lists depositable plans →
  `SavingsDepositSheet`. New `/home/kids/[kidId]/savings/[depositId]`
  detail page (value, chart reusing `LotChart`, lock status + unlock
  date, withdraw button — disabled "Locked for now" until maturity).
- **Verified**: full backend suite 118 passed (was 101; +17 in
  `test_savings_service.py` / `test_savings_plans.py`). `npm run
  build` + `npm run lint` clean. Live-tested with Playwright against a
  real dev server + the synthetic test family (minted NextAuth cookie
  per the "Lessons learned" recipe): created plans via the form,
  deposited into flexible + locked, opened both detail pages, withdrew
  the flexible one (cash round-tripped correctly), confirmed the locked
  one blocks withdrawal — zero console errors.
- **Ghost-port bug bit again**: port 8098 (this worktree's backend per
  `.env` at session start) had two listeners — a real one and an
  unkillable ghost from a prior session serving stale code (openapi had
  no savings routes). Moved the whole stack to **8099** (updated
  `frontend/.env.local`, restarted both servers). If backend calls 404
  on savings routes, check `netstat` for a ghost on the configured port
  before assuming a code problem.
- **Second round (same session, user feedback): split + presets.** The
  single "Savings plans" settings screen was split into **two** — the
  hub now has separate "Flexible savings" and "Locked savings" cards,
  each with its own `Active` pill (true if ≥1 active plan of that kind)
  and its own page at `/home/settings/investing/savings/[kind]`
  (`kind` = `flexible` | `locked`, one shared `SavingsKindForm`
  component). Each page leads with **ready-made preset plans** the
  parent switches on/off with a checkbox — they don't have to invent
  one. Presets live in `savings_service.PRESET_PLANS` (code, not
  seeded): flexible "Everyday savings" 1%/mo; locked 1mo/1.5%,
  3mo/2%, 6mo/2.5%, 12mo/3%. Migration `0013` adds
  `savings_plans.preset_key` (NULL = a custom plan the parent typed).
  `POST /family/savings-presets` `{key, active}` toggles one:
  activating creates-or-reactivates the family's plan row for that
  key; deactivating **deletes** the row if empty, or just flips
  `is_active=false` if a kid still has money in it (their deposit keeps
  growing regardless). `GET /family/savings-presets` is the static
  catalog. Custom "Add your own" form is still there under the presets,
  now kind-scoped (no lock stepper on the flexible page; locked
  defaults 6 months / 3%). Kid's Save tab groups plans under
  **Flexible** / **Locked** headings. 21 savings tests pass, full
  suite green, build/lint clean, re-verified live with Playwright
  (toggled presets on both pages, confirmed hub pills + kid Save tab).
- **Third round (same session, more feedback):**
  - **Custom in-app confirm sheet** (`components/ui/confirm-sheet.tsx`,
    `ConfirmSheet`) replaces `window.confirm()` for savings actions —
    amber-toned (new `--color-tint-brass` / `--color-brass-dark` tokens,
    derived from the existing `--color-brass` accent), calmer than
    `SellAndRebuySheet`'s red. Used for plan-delete and the new
    cash-out.
  - **Bulk cash-out**: `POST /family/savings/cash-out` `{kind}` closes
    every open deposit of that kind (flexible / locked), for every kid,
    paying each back to that kid's cash — **overrides the maturity lock
    on locked deposits** (parent's own money to release). Button shows
    on each kind's settings page only when that kind has open deposits.
    `savings_service._close_deposit` is the shared helper (normal
    withdraw enforces maturity, cash-out doesn't).
  - Preset section heading "Ready-made plans" → **"Recommended plans"**.
  - The flexible preset renamed "Everyday savings" → **"Flexible plan"**
    (preset_key stays `flex`, so already-activated rows are unaffected
    until re-toggled).
  - Custom ("Your own") plans now have an **activate checkbox** too
    (was delete-only) — just a `PATCH {is_active}`.
  - Kid portfolio + deposit-detail: locked vs flexible deposits get a
    small tinted padlock pill (`components/ui/savings-badge.tsx`,
    `SavingsKindBadge` — closed padlock + amber for locked, open
    padlock + emerald for flexible/unlocked).
  - No new migration this round. 13 `test_savings_plans` + 10
    `test_savings_service` pass; build/lint clean; re-verified live
    (amber sheets, cash-out actually emptied the deposits, badges
    render).
- **Fourth round (same session):**
  - **Kind settings pages are now a staged form.** Preset + custom-plan
    checkboxes only change local state; a **"Save changes"** button
    (appears when dirty) commits them. On Save, if any change switches
    OFF a plan a kid still has money in, `SavingsChangesSheet` (amber)
    opens with a per-kid breakdown (`GET
    /family/savings-plans/{id}/deposits`) and two choices: **"Cash out &
    turn off"** (`POST /family/savings-plans/{id}/cash-out` per affected
    plan, then apply) or **"Turn off, keep the savings"**. Staged state
    resets via the adjust-state-during-render pattern when the server
    `plans` signature changes after refresh.
  - The page-wide "Cash out every X deposit" button from round 3 was
    **removed** (user didn't want it) — cash-out is now only per-plan,
    surfaced inside the Save confirm sheet. `savings_service.cash_out_kind`
    → `cash_out_plan`; added `plan_deposit_breakdown`.
  - A plan that's **off but still holds deposits** shows an orange,
    tap-to-explain **`StillGrowingBadge`** ("N still saving") instead of
    the plain muted text — same tap-to-reveal idea as the boost badge.
    The hub's kind card shows an orange **"Savings still growing"** pill
    (vs. green "Active") in the same situation.
  - Delete still uses its own immediate `ConfirmSheet` (that already had
    a popup — round-1 point was only about the checkboxes).
  - `plan_deposit_breakdown`'s Kid-name lookup: `session.execute(...)`
    returns a `Result`, not subscriptable — must iterate it into a dict
    (`{k: v for k, v in await session.execute(...)}`), don't `dict(...)`
    it directly.
- **Fifth round (frontend only, no backend/migration change):**
  - The kind settings pages' **"Save changes" button is now a sticky bar
    pinned to the top** of the scroll area (only when there are staged
    changes) — the user wanted it visible without scrolling.
  - The pre-save confirm gate is **gone**. Save just applies the toggle
    changes; then, if any switched-off plan of that kind still holds a
    deposit, `SavingsLeftoversSheet` (renamed from `SavingsChangesSheet`)
    opens as a **post-save** prompt listing each such plan with a per-kid
    breakdown and two buttons per plan — **"Cash out"** (`POST
    /family/savings-plans/{id}/cash-out`) or **"Switch back on"**
    (`POST /family/savings-presets` for a preset, `PATCH
    {is_active:true}` for a custom plan) — plus "Done". This is the
    **only** place cash-out is offered now (no standalone button on the
    page). To find the leftovers after Save, it re-fetches
    `/family/savings-plans` directly rather than waiting out
    `router.refresh()`.
  - The hub's orange **"Savings still growing"** pill is now a tappable
    `HubStillGrowingBadge` — tap reveals a one-liner, same pattern as
    the boost badge / the per-plan `StillGrowingBadge`.
- **Sixth round (frontend only):**
  - **Every** plan card in the kind settings pages now shows a
    deposit-count marker when it has open deposits — `PlanDepositMarker`
    (renamed/generalised from `StillGrowingBadge`): a plain emerald
    "N deposits" pill for an active plan, the orange tap-to-explain
    "N still saving" for a switched-off one.
  - Fixed the "still growing" copy (both the per-plan badge and the
    hub's `HubStillGrowingBadge`): a leftover deposit is redeemed by the
    **kid from their own savings screen**, not from Settings — and a
    **locked** one only once its term is up. (The post-save
    `SavingsLeftoversSheet` is the only place Settings can act on one,
    and only in that moment.)
- **Seventh round (frontend only) — user reversed the round-6 stance:**
  a switched-off plan card that still has deposits now shows a small
  outlined **"Cash out"** button next to its "N still saving" marker.
  Tapping it fetches the per-kid breakdown and opens an amber
  `ConfirmSheet` ("Cash out '<name>'?" → "Cash out now"), which calls
  the existing `POST /family/savings-plans/{id}/cash-out` (overrides the
  lock for a locked plan — the confirm copy says so). Copy on the
  per-plan badge + hub badge updated to say the parent *can* cash it out
  from settings again, alongside the kid's own withdrawal.
- **Eighth round (frontend only):**
  - Hub savings cards now show up to two status pills: a **brass
    "Deactivated"** (kind has plans but none switched on) and a
    **red "N still growing"** (leftover deposits in a switched-off plan)
    — the "still growing" one moved from brass to red
    (`tint-negative`/`negative`) so it reads as more urgent than plain
    "Deactivated". Both tap to explain. `hub-still-growing.tsx` →
    `hub-savings-badges.tsx` (`HubDeactivatedBadge` +
    `HubStillGrowingBadge`). The per-plan `PlanDepositMarker`'s
    inactive "N still saving" pill went red to match.
  - **The post-save leftovers sheet now only fires for a plan *this
    save* switched off** that has deposits — `turnedOffWithDeposits()`
    computed from staged-vs-server before applying, replacing the old
    "re-scan every off-with-deposits plan" (`loadLeftovers`). Turning a
    *different* plan on and saving no longer pops an alert about a
    pre-existing switched-off plan.
- **Ninth round — React duplicate-key bug fix:**
  `savings_service.plan_deposit_breakdown` returned one row *per open
  deposit*, so a kid with two deposits in the same plan produced two
  rows with the same `kid_id` → "Encountered two children with the same
  key" in `SavingsLeftoversSheet` / the cash-out ConfirmSheet (both key
  by `d.kid_id`). Now aggregates per kid (values summed, one row). No
  API-shape change; new test
  `test_plan_deposits_breakdown_sums_a_kids_multiple_deposits_into_one_row`.
- **Deferred, still**: "interest from parent" as a *separate* flat
  cash-balance rate — this savings-plans feature is the more general
  version of that idea, so it may now be moot; confirm with the user
  before building it.
- **Not done (needs user confirmation)**: push `savings-plans`, merge to
  `master`, cut the next branch.

## Status as of 2026-09-07 — stock boost feature merged to worktree's branch (backend v1.6.0 / frontend v0.7.0)

**The stock-boost feature (full detail in the "stock boost feature" status
entry below — this is the finish-feature/merge wrap-up, not a re-description)
is done, merged with `origin/master`, reviewed, and ready to merge to
`master`.** Built entirely in `FamilyBank-worker-3` on branch
`boosted-stocks-and-interest`; `master` had meanwhile diverged substantially
(production-latency investigation, request-log retention, rate limiting,
frontend loading/error boundaries, an Android TWA wrapper — none of it
touching the boost feature's own files directly, but several of them
touched the *same* functions this feature also rewrote).

- **Merging in `origin/master` required real conflict resolution, not just
  accepting a side.** Three files had literal conflict markers:
  - `CLAUDE.md` — both branches had appended their own dated "Status as
    of" section on top of the same shared history; resolved by keeping
    both, newest first, and disambiguating the two identically-dated
    "2026-09-06" headings (one for this feature, one for the pre-existing
    request-logging/currency-history work) since master's own new content
    made a bare date no longer unique.
  - `backend/app/scheduler/jobs.py` — master had split the old
    `_refresh_prices()` into `_fetch_prices()`/`_write_prices()` (a perf
    fix, to avoid holding a DB connection open during the ~10s of external
    HTTP calls) and added `RequestLog` cleanup; this branch's `PriceTick`
    insert (needed for boost_service to have tick history to walk) had to
    move into master's new `_write_prices()`, right after its `PriceCache`
    upsert, rather than living in the now-deleted monolithic function.
  - `backend/tests/test_investing_service.py` — two separate real
    conflicts, not just noise: (1) master's
    `test_buying_twice_averages_cost_and_sums_units` had a name and
    docstring describing the *old* avg-cost blending behavior, but its
    actual body already asserted the *new* per-lot behavior (two distinct
    lots, two distinct lot_ids) — kept this branch's correctly-named
    `test_buying_twice_creates_two_separate_lots` instead (same body,
    honest name) alongside master's genuinely new, unrelated
    `test_buy_rejects_cleanly_when_fx_rate_is_missing`. (2) master's
    `test_since_purchase_pct_reflects_total_return_not_last_tick_change`
    mutated `PriceCache` directly and cleared the price-context cache,
    which was correct for the *old* avg-cost `since_purchase_pct` (still
    computed from live `PriceCache`) but wrong for a lot, whose
    `since_purchase_pct` this feature computes from `boost_service`
    walking `price_ticks` instead (see `investing_service._lot_entry`) —
    kept this branch's `_add_tick`-based version, the only one that
    actually exercises the code path a lot-based holding uses.
  - **`backend/app/services/investing_service.py` and
    `backend/app/api/routes_investing.py` auto-merged with no conflict
    markers, but the result was still broken** — worth internalizing:
    a clean textual 3-way merge is not proof of a semantically correct
    one when both branches rewrote the same functions for different
    reasons (this branch: per-lot buy/sell; master: routing every price
    read through `load_price_context()`/`ctx.prices.get()` instead of
    live per-call queries, and replacing separate `get_kid`+`get_family`
    dependencies with a combined `get_kid_and_family`). Running the test
    suite immediately after the merge commit caught it: `routes_investing.sell_all`
    still used the pre-merge `Depends(get_family)` pattern, but master's
    side of the merge had dropped `get_family` from this file's imports
    entirely (replaced by the combined dependency) — `NameError: name
    'get_family' is not defined` at import time, which means the whole
    app would have failed to even start. Fixed by switching `sell_all` to
    the same `KidAndFamily`/`get_kid_and_family` pattern every other route
    in this file already uses. **Lesson: after resolving a merge with any
    auto-merged (marker-free) file that both branches touched
    substantively, run the test suite before trusting the merge — don't
    assume "no conflict markers" means "no conflict."**
- **Verified after the merge, not just assumed clean:** all 101 backend
  tests pass (`cd backend && pytest`, up from the 65 mentioned in an older
  status entry below — most of the growth is this feature's own
  `test_boost_service.py`/`test_boost_settings.py` plus expanded
  `test_investing_service.py` coverage), `alembic upgrade head` applies
  cleanly against the shared dev/test DB (already at `0011`, migration
  chain `0009→0010→0011` intact now that the real `0010_request_logs.py`
  replaced this branch's placeholder), and `npm run build`/`npm run lint`
  are both clean.
- Reviewed every backend file in the diff line-by-line plus the bulk of
  the frontend components as part of this same pass (both the "senior dev
  review" and "self code review" steps of this project's finish-feature
  workflow, done together rather than as two separate passes) — found
  exactly the one real bug above (the dangling `get_family` reference);
  nothing else worth flagging turned up (no dead code, no debug leftovers,
  no unused imports — grepped for all three across the full feature diff).
- Backend bumped 1.5.0 → 1.6.0, frontend 0.6.0 → 0.7.0 (both minor: a real
  new user-facing feature, not a patch-sized fix).
- **Not yet done as of this entry**: push the branch, merge to `master`,
  cut the next branch — gated on explicit user confirmation per this
  project's permissions (destructive/shipping steps are never taken
  autonomously here). If you're reading this and those still haven't
  happened, that confirmation is the next thing blocking this feature
  from reaching production.

## Status as of 2026-09-07

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

## Status as of 2026-09-06 — stock boost feature

**Stock "boost" feature — backend built and tested, settings UI built and
manually verified; kid-facing portfolio UI NOT yet wired up (see gap
below).** Born from a user request to make small stock positions feel
less boring, without literal leverage (rejected — too much real downside)
or a cosmetic-only multiplier (rejected — doesn't compete economically
with the separately-planned "interest from parent" idea, deferred this
round). Landed design: a family-wide `boost_buffer_rate` (monthly %,
`families.boost_buffer_rate`) that only ever *adds* to a stock's return
on a tick where the real price rose — never on a down-tick, so real
daily volatility/downside is untouched, only the long-run expected value
is tilted up.

- **New `price_ticks` table** (`app/models/catalog.py`): append-only,
  one row per symbol per scheduler refresh, written alongside the
  existing overwrite-only `PriceCache` in `scheduler/jobs.py`. This is
  what makes the boost math possible at all — `PriceCache` only ever
  has "now", so there was previously no way to reconstruct a stock's
  path since a specific purchase moment.
- **New `investment_lots` table** — every stock purchase now creates its
  own permanent, independent lot (`investing_service.buy()` no longer
  writes to the old `investment_holdings` avg-cost table at all,
  boosted or not — this was a deliberate scope decision made with the
  user: unify on one model rather than keep two, since a lot's fixed
  purchase timestamp is what makes a real "since purchase" graph
  possible for every holding, not just boosted ones). Two purchases of
  the same symbol are never blended — they show up as two separate
  entries, sellable independently (partial sells reduce a lot's units;
  selling to zero closes it). Old `investment_holdings` rows from before
  this shipped are untouched and still sellable via the legacy code path
  in `investing_service.sell()` (dispatches on `lot_id` vs `symbol`).
- **`boost_service.py`'s `_walk`/`compute_lot_series`/`compute_lot_value`
  — deliberately stateless.** No persisted checkpoint or accrued-factor
  column anywhere: a lot's whole synthetic trajectory (and thus its
  current value *and* its since-purchase graph — same function, one
  returns the last point, the other the whole series) is recomputed from
  scratch on every read, by walking `price_ticks` from the lot's
  `purchased_at`. This was a real back-and-forth with the user — the
  first design tracked a separately-maintained "boost factor" applied to
  the live current price, which turned out to be the wrong shape (it
  couldn't produce one coherent "real value including the boost
  throughout the whole period," and needed a write-on-read checkpoint,
  which is exactly the FastAPI-autobegin trap in "Lessons learned"
  below). Full recompute is only viable because of the scale this app
  runs at (a family has at most a couple dozen open lots; a symbol
  accrues a few thousand ticks/year) — don't copy this pattern
  somewhere with real per-user volume without reconsidering it.
- **The rate is family-wide, not per-kid or per-symbol**, and can only be
  set/changed while *every* kid in the family holds zero stock at all
  (legacy holdings or open lots — `investing_service.has_open_positions`,
  enforced in the new `PATCH /family/settings/boost-buffer-rate`). This
  guarantees every lot open at any moment shares exactly one rate — no
  mid-holding rate change to reason about. The user wants this
  auto-sell-then-rebuy-at-the-new-rate eventually; for now the parent
  has to sell everything by hand first.
- **The per-tick bonus is prorated by real elapsed wall-clock time**
  (`HOURS_PER_MONTH = 730.5`), not a fixed assumed tick count — the
  scheduler's tick spacing is irregular (a relative sleep loop that
  stops entirely while the backend process is idle, see
  `scheduler/loop.py`), so a fixed "%/tick" would over- or under-shoot
  depending on how often the process happened to be awake.
- **Settings UI — two-tier structure, iterated live against direct user
  copy feedback (treat as production-bound text, not placeholder).**
  `/home/settings/investing` is a hub page (currently just one card) —
  a short marketing-style pitch for "Stock boost" plus a button to
  `/home/settings/investing/boost`, which holds the actual controls
  (`boost-settings-form.tsx`): toggle, a 0.1%-stepped rate input (short
  recommendation line, default 3.0%), two short plain-language
  paragraphs on what the boost does, and a worked dollar example ("$50
  into the S&P... about $51 without a boost, about $52.50 with one").
  This hub/sub-page split is deliberate groundwork for the deferred
  interest feature to slot in as a second card later — see spec at the
  top of `investing/page.tsx`. Linked from a "Advanced investing &
  savings settings" row on the main Settings page, no subtitle (an
  earlier version named the not-yet-built interest feature there, which
  the user asked to remove since it isn't real yet).
  **A real copy correction worth remembering**: an earlier draft framed
  the boost as "not coming from the market, coming from you" as if
  market gains were somehow different — the user caught that this
  contradicts the app's own core framing (spec section 0): *everything*
  here is virtual, so a "real" market gain is exactly as much "from the
  parent" as a boosted one is. Reframed to avoid that false contrast
  entirely — the example now just calls the extra "your treat on top,"
  warmly, not a solemn warning about who's really paying. If writing
  parent-facing copy about any gain/cost in this app, re-check it
  against that same framing before shipping it.
  Manually verified against a live dev server with Playwright
  (screenshots + a real save/reload round-trip against the DB, and the
  hub→boost-page click-through) — see "Lessons learned" below for how
  the auth was faked for that, since it's a reusable trick.
- **Fixed same-day, and worth flagging exactly how it was missed:**
  `SellSheet` and the buy/sell screens still sent the old `{symbol,
  units}` shape after `buy()` was rewired to lots — since a symbol can
  now match more than one lot, this wasn't just "the UI looks slightly
  off," it was a hard functional break: selling *any* stock bought after
  this shipped failed outright (no legacy `InvestmentHolding` row for it
  to find), and two purchases of the same symbol were indistinguishable
  in the UI (both linked to one page that could only ever act on
  whichever one happened to match first). Fixed by threading `lot_id`
  through: `portfolio-client.tsx`'s per-row link now carries
  `?lot=<lot_id>`; `buy/[symbol]/page.tsx` resolves the specific
  clicked holding from that instead of a bare `.find(h => h.symbol ===
  symbol)`; `SellSheet` sends `lot_id` when present, `symbol` only for
  a genuine pre-feature legacy holding. Verified for real with
  Playwright against a live dev server: bought the same symbol twice,
  confirmed two distinct rows/URLs, sold one, confirmed via the API
  that only that exact lot closed and the other was untouched.
  **Why the backend test suite passing didn't catch this**: the API
  test that exercises buy→sell was itself updated, as part of the same
  change, to send the new `lot_id` shape — which proves the backend
  handles a well-formed request correctly, but says nothing about
  whether the actual frontend still constructs one. A backend-only
  "tests pass" claim after changing a request/response contract that
  existing frontend code depends on is not the same as verifying that
  frontend code — the fix is to actually click through any *existing*
  screen whose backend contract changed, not just a screen whose files
  you touched directly.
- **Per-lot graph screen — built, then became the canonical "view/sell an
  owned lot" screen after user feedback.** `/home/kids/[kidId]/lots/[lotId]`
  (`lot-chart.tsx` — a plain inline SVG polyline, deliberately not a
  charting library for one simple line) renders the exact same `series`
  `boost_service.compute_lot_series` produces, so the chart and the
  headline number can never disagree.
  First version linked it from a "Chart" link inside the *Buy* screen's
  "you own this" banner — the user then pointed out (with a screenshot)
  that a screen titled "Buy AMZN" showing a buy form was wrong for
  viewing an *already-owned* position, and that its sparkline was the
  generic asset-level one, not a since-purchase graph. Root cause:
  `portfolio-client.tsx`'s "My Investments" rows still linked every
  holding to the Buy screen. **Fixed by routing differently based on
  what a holding actually is**: a lot (`lot_id` present) now links
  straight to `/lots/[lotId]` — no buy form ever shown, and the correct
  purchase-scoped chart, both automatically, since that page never had
  a buy form or generic sparkline to begin with. Only a pre-lot legacy
  avg-cost holding (no `lot_id`, can't have its own detail page) still
  goes to the Buy screen's banner. Sell itself was also moved onto the
  lot page directly — `SellSheet` is now opened from `lot-detail-client.tsx`
  instead of round-tripping through `/buy/[symbol]?lot=...`, which stays
  reachable but is no longer how a real user gets there.
  Also added, from the same feedback: a tap-to-reveal explanation on the
  "Boosted X%/mo" badge (kept to just this page, not the list rows,
  since nesting a button inside `portfolio-client.tsx`'s `<Link>` risks
  both an a11y issue and swallowed/ambiguous click handling — a static
  badge there is the safer trade-off).
  **A real bug found via testing this, not requested but worth fixing
  immediately since it shipped in the same change**: a fully-sold lot's
  `units` drops to 0 (see `_sell_lot`), so `current_value * units` on
  the detail page rendered a misleading "$0.00" for anything sold in
  full. Fixed two-sided: `boost_service.compute_lot_series` gained an
  `until` parameter so a closed lot's history is capped at `sold_at`
  instead of continuing to "move" from ticks that landed after the kid
  no longer held it, and `get_lot_detail` now returns the already-
  captured `sale_value`/`sold_at` for a closed lot rather than trying
  to recompute a value from (now correctly near-empty) post-sale
  history. The frontend shows a closed lot's per-unit sale price
  instead of a total, since the original unit count is gone once units
  hits 0.
  Verified with synthetic `PriceTick` rows inserted directly (real
  ticks take hours to accumulate), including one deliberately dated
  *after* a full sell, to confirm the closed lot's number and chart
  both ignored it.
  **One more round of feedback on the same screenshot**: the sell UI
  itself was a "Sell this" button opening a `SellSheet` popup — asked to
  drop the popup entirely in favor of a direct "Sell all" action plus
  the picker (units stepper, proceeds, confirm) shown inline on the page
  at all times. Extracted the picker into a new `sell-controls.tsx`
  (shared by both the inline lot page and the still-popup-based
  `SellSheet` used on the Buy screen for legacy holdings) so the same
  math/API-call logic isn't duplicated — `SellSheet` is now just
  `BottomSheet` + `SellControls`. The picker's own internal shortcut was
  relabeled "Max" (was "Sell all") to avoid two same-labeled controls on
  one screen now that a real "Sell all" button exists above it.
  **Then simplified further, and re-colored**: the standalone "Sell all"
  button was actually dropped again — merged into the picker's own
  confirm button instead, which now reads "Sell all for $X" when the
  stepper is at max units and "Sell for $X" otherwise, and switched from
  `bg-emerald` (this app's buy/positive color) to `bg-negative`
  (matches "Deduct"'s styling in `debt-sheet.tsx`) since a sell action
  reading in green looked wrong to the user. This removed the whole
  two-button/divider structure entirely — one control, correctly colored.
  Also from the same feedback round: the hub page
  (`/home/settings/investing`) now fetches `FamilySettings` and shows a
  small "Active" pill on the Stock boost card when a rate is set, so a
  parent can see status without a click; the boost page's toggle row was
  relabeled "Boost active" (was "Boost stock gains" — reads as a state,
  not an instruction); and a successful save now `router.push`es back to
  `/home/settings` instead of leaving the parent stranded on the boost
  page — chosen specifically to avoid adding any new UI element for
  "how do I get back", per the user's ask to not overload this screen.
- **One more pass on the boost page + two new features, from a fresh
  round of screenshots.** The "Boost active" label was itself corrected
  again to **"Stock boost active"** — don't re-shorten it. The
  explanation/rate-picker/example were unconditionally hidden behind
  `{enabled && ...}`; changed to always render regardless of the
  toggle, since a parent should be able to read what this does and
  preview a rate *before* deciding to turn it on. The back chevron
  (`PageHeader`'s `backHref`) now skips the one-card hub and goes
  straight to `/home/settings` — asked for "a faster way back," and
  since the hub has nothing worth stopping at with only one card in it,
  skipping it outright (not just after a save) was the actual fix, not
  the router.push-on-save from the previous round alone.
  **New: a portfolio-wide "Sell everything" button** on the kid's
  My Investments tab (`portfolio-client.tsx`) — backed by a new
  `investing_service.sell_all()` / `POST /kids/{id}/sell-all` that
  closes every open lot and legacy holding for a kid in one call (reuses
  `_sell_lot`/`sell()` per position, not a new sell code path). Has a
  native `confirm()` — the only sell action in this feature with one,
  since liquidating an entire portfolio in one tap is meaningfully more
  consequential than any single-lot sell.
  **New: the "Boosted X%/mo" tappable badge now also appears on the Buy
  screen** (not just an owned lot's own pages) — extracted into shared
  `ui/boosted-badge.tsx` (`BoostedBadge` + `BoostedExplanation`, both
  now used by `lot-detail-client.tsx` and `buy-form-client.tsx`) so
  buying a new stock shows upfront that it'll be boosted, using the
  family's current `boost_buffer_rate` rather than a specific lot's
  locked-in one (the purchase hasn't happened yet).
- **Fourth feedback round — three UI fixes plus the sell-and-rebuy
  feature that earlier notes flagged as a "future" possibility.**
  (1) "Sell everything" now shows the amount (`Sell everything for
  $X`, using `portfolio.holdings_value` — already the exact right
  number, no new calculation needed).
  (2) **The Buy screen no longer offers Sell at all**, even for a
  symbol the kid already owns — browsing to buy and managing an
  existing position are different intents, and conflating them was the
  root cause of an earlier session's "Buy AMZN" screen showing a Sell
  button. Now: `sellableHolding` in `buy/[symbol]/page.tsx` is only ever
  non-null when `from === "holdings"` *and* the match is a legacy
  avg-cost holding (no `lot_id`) — the sole remaining case this screen
  sells directly, since a legacy holding has no dedicated page of its
  own the way a lot does. Every other case (browsing to buy, or already
  owning lots) shows a plain "You already own N units, worth $X" line
  with no interactive element at all — no Sell, no Chart link.
  (3) **Two real bugs found from one user report, both now fixed**: (a)
  `SellControls`' unit stepper got stuck after a partial sell — the
  component doesn't unmount across a `router.refresh()`, so its
  `unitsStr` state kept the pre-sell value even though `holding.units`
  (the prop) had shrunk, clamping both +/- buttons disabled. Fixed by
  adjusting state during render when `holding.units` changes (React's
  documented pattern for this — a `useEffect` calling `setState`
  synchronously trips this project's lint rule and is the wrong tool
  here regardless). (b) Selling from the lot detail page — full or
  partial — now navigates to `/home/kids/{kidId}` afterward instead of
  staying put; a sell's natural conclusion is returning to the
  portfolio, not lingering on a now-stale single-lot page.
  (4) **New: `investing_service.apply_boost_rate_change_with_rebuy` +
  `POST /family/settings/boost-buffer-rate/sell-and-rebuy`** — the
  "future" auto-migration mentioned in earlier status notes, now built.
  Snapshots every kid's every position (symbol + units, lots and legacy
  holdings alike) *before* selling anything, sells everything for every
  kid, changes `family.boost_buffer_rate`, then rebuys each snapshotted
  position at the new rate. No new commit inside the function — the
  route's single outer commit is what makes the whole migration atomic
  (any failure mid-way rolls every sell/buy/rate-change back together,
  same mechanism already relied on elsewhere in this file). Surfaced on
  the boost settings screen as a small red "⚠ Sell everything and rebuy
  with the new boost" line that appears only after the normal save hits
  the existing 409 guard — clicking it opens a `confirm()` spelling out
  exactly what will happen (matches this app's existing convention for
  consequential actions, e.g. `handleRemoveKid`) before calling the new
  endpoint. Verified live end-to-end: rate changed family-wide, the same
  symbol/unit count came back under a **new** lot id (proving it was
  genuinely re-sold and re-bought, not just relabeled), and cash netted
  back to the pre-sell amount since sell and rebuy happen at the same
  price.
- **Fifth feedback round, two more fixes.** (1) The lot detail page was
  missing the asset's description text that the Buy screen already
  shows (e.g. "Amazon started as an online bookstore...") — added
  `description` to `LotDetailOut`/`get_lot_detail` (sourced from
  `AssetCatalog.description`, same field the catalog/buy screens
  already use) and rendered it on `lot-detail-client.tsx` in the same
  spot the Buy screen uses. (2) The sell-and-rebuy confirmation used a
  bare browser `confirm()` — replaced with a proper in-app sheet
  (`sell-and-rebuy-sheet.tsx`, red/warning-toned, a numbered list of
  exactly what will happen, `bg-tint-negative`/`text-negative` matching
  this app's existing warning-color tokens rather than introducing a
  new one) — `boost-settings-form.tsx` now opens this sheet instead of
  calling `confirm()` directly, and only actually calls the endpoint
  from the sheet's own confirm button.
- **Sixth round: a copy pass on the boost settings page itself — flagged
  by the user as still a draft, not finalized.** The hub card's short
  teaser now also repeats right under the "Stock boost active" toggle.
  Added a new opening paragraph stating the actual purpose (make gains
  more visible/felt) plus a comparison to savings interest (recommend
  setting the boost at least 1% above whatever savings rate is offered,
  written to make sense even before the deferred interest feature
  exists). Replaced the vague "cheering your kid on" paragraph — user
  called it poorly worded — with a plain, light-touch warning that the
  rate compounds *monthly*, so it adds up on a large balance over time.
  The example's math changed too: it previously assumed the *entire*
  nominal rate applies every month, which is wrong (the boost only
  accrues on up-ticks — see `boost_service._walk`) and used a 2%/month
  "typical" gain the user correctly flagged as unrealistic for the
  S&P 500 (real long-run average is closer to 0.8%). Now uses 1%/month
  and shows the proration explicitly (illustrative "about two-thirds of
  days were up, so about two-thirds of the rate applied") rather than
  implying the full rate always lands — `EXAMPLE_MONTHLY_GAIN_PCT` and
  the new `EXAMPLE_UP_DAY_FRACTION` constant in `boost-settings-form.tsx`
  drive this. If asked to touch this copy again, re-read this whole
  entry first — several of these were direct corrections to an earlier
  version that looked reasonable in isolation but didn't hold up.
- **Seventh round — a straight copy-editing pass, not a content
  change.** The user called out the previous round's prose as reading
  visibly AI-written: the same em-dash "setup — payoff" rhythm repeated
  in nearly every paragraph, plus one paragraph phrased as "not just
  X — Y" antithesis. Tightened every paragraph to vary sentence rhythm
  and cut redundant clauses (the example went from three em-dashes to
  one). The hub card's teaser, added to this page two rounds ago at the
  user's own request, was removed again on their own follow-up call —
  it's back to living only on the hub. The monthly-compounding warning
  was also corrected on substance, not just style: it originally said
  "adds up every month, not just once," which the user pointed out is
  backwards — the *configured rate* is monthly, but what a kid actually
  earns lands in small *daily* pieces (matches the "~0.10% added on a
  day it's rising" line already on this page) — now reads "The rate is
  monthly, but your kid earns it in small daily pieces." If touching
  this copy again, preserve that rhythm variety rather than reverting
  to a uniform em-dash pattern.
- **Eighth round — two more corrections on the same page.** The purpose
  paragraph still didn't land; the user asked for it to literally open
  with "The idea behind the stock boost is..." — done verbatim. The
  monthly-compounding line was missing the actual point: the user
  wants a parent to viscerally register that 3%/month is enormous
  next to a real-world savings rate (quoted per *year*), without
  sounding alarmist. Added a live, rate-dependent calculation — new
  `RATE_CONTEXT_AMOUNT` (1000) and `yearlyBoostOnRateContext =
  1000 * ((1 + rate/100)**12 - 1)`, using whatever rate the stepper is
  *currently* on (not the fixed `RECOMMENDED_RATE` the worked Example
  box anchors to) — so the paragraph updates live as the parent moves
  the stepper: "At 3.0%/month, $1,000 held for a year earns about
  $425.76 from the boost alone." A concrete, moving number in context
  does the "this is a lot" job better than another adjective would.
- **Deferred by explicit user request, not forgotten:** "interest from
  parent" (a simpler flat monthly rate on cash balance, meant to compete
  economically with the stock boost) — discussed at length but
  intentionally out of scope for this round.

**Migration numbering collision across parallel worktrees actually
happened this session — worth internalizing, not just the abstract
warning below.** While building the above, `alembic upgrade head` was a
silent no-op: another worker session (`observability-logging` branch, a
different worktree entirely) had already claimed revision `0010` for an
unrelated `request_logs` table and run it against the *shared* dev/test
DB before this branch's own `0010` file existed. Alembic matches
revisions by the `revision` string, not the filename or which worktree
wrote it — so this branch's different `0010` content was treated as
"already applied" and silently never executed, with no error. The fix
was renumbering this branch's real migration to `0011`, and — since the
other worktree's actual file was uncommitted and unreachable from here —
reconstructing a best-effort placeholder `0010_request_logs_placeholder.py`
(schema introspected directly off the live shared DB) just so this
worktree's own alembic graph resolves. **That placeholder must be
deleted once the real `0010_request_logs.py` lands on master** (confirmed
with the other worker over cross-session messaging) — check
`alembic/versions/` for a duplicate `0010` before merging this branch.
Lesson: checking `versions/` for the next free number (as this file
already says) isn't enough when several worktrees share one live DB —
the actual danger is a same-numbered revision from an *uncommitted*
migration in another worktree already having run against the shared DB,
which a `git`-only check can't see. Run `alembic current` against the
shared DB, not just `ls versions/`, before trusting a number is free.

## Status as of 2026-09-06 — request logging, currency history, and earlier work

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
- **The ghost-port issue above recurred multiple times in one session**
  (2026-09-06, same worktree) — and this time it was caught with hard
  evidence of the actual mechanism: `Get-NetTCPConnection -LocalPort
  <port>` returned **two different PIDs both `Listen`ing on the exact
  same port simultaneously** (confirmed via `netstat` too). One was a
  genuinely fresh `uvicorn --reload` process (verified via
  `Get-CimInstance Win32_Process`'s `CommandLine` — a real, current
  process, not a phantom), the other an old one that should have died
  when a prior `Stop-Process` ran but evidently didn't. Requests were
  routed to *whichever one felt like answering* — so a fresh restart,
  even a *verified* fresh restart with a clean startup log, is not
  proof you're talking to it: `curl` a field/endpoint you know only the
  new code has (not just "does it respond") before trusting a restart
  actually took effect. `Get-CimInstance` failing to resolve a PID that
  `netstat`/`Get-NetTCPConnection` shows as `LISTENING` is the tell that
  a second, unkillable listener exists — don't waste time trying to
  identify or kill it (both attempts failed again this session); move
  the whole stack to a brand-new port instead (update both
  `frontend/.env.local` **and** restart the frontend process itself,
  since Next.js only reads `.env.local` at process start, not on hot
  reload) and get on with it. Treat "the running server disagrees with
  the code on disk" as this issue by default on this project before
  assuming a real regression.
- **To screenshot a page behind `requireSession()` without real Google
  OAuth**: mint a backend JWT with `issue_session_token(...)` (as the
  synthetic test family), then separately mint a matching Auth.js v5
  session cookie with `next-auth/jwt`'s `encode({ token: { backendToken,
  familyId, baseCurrency, sub }, secret: process.env.AUTH_SECRET, salt:
  "authjs.session-token" })` — `salt` must be the literal cookie name,
  not a random value. Set that as a `Playwright` context cookie
  (`name: "authjs.session-token"`, `domain: "localhost"`) before
  `page.goto(...)`. Two gotchas that ate real time: (1) the `encode`/
  Playwright script needs to run with Node resolving modules from
  `frontend/`'s own `node_modules` (write it into that directory, not
  a temp dir, or `require("next-auth/jwt")` fails) and needs real
  Windows-style paths (`C:/...`), not git-bash's `/c/...` — a path
  embedded in JS source doesn't get MSYS's automatic argument rewriting;
  (2) the frontend and backend dev ports must actually match what
  `backend/.env`'s `CORS_ORIGINS` allows, or every client-side `fetch`
  silently fails as a CORS preflight rejection that looks nothing like
  an auth problem.
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
| `FamilyBank-worker-3` | 8097 (rotated *five* times across 2026-09-06–07 — 8091→8094→8095→8096→8097 — chasing the ghost-listener bug below, which keeps recurring even on a genuinely fresh `--reload` process; check `netstat`/`Get-NetTCPConnection`/`frontend/.env.local` for the current truth rather than trusting this table, and don't be surprised if it's moved again. Given how often `--reload` alone has turned out to be lying about serving current code this session, **prefer a full kill-and-restart over trusting a reload notice** before believing a route/field is "still missing") | 3013 |

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
