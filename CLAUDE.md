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

## Status as of 2026-09-06

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

**Built and verified:** the full v1 flow — Google-only sign-in →
onboarding (currency + first kids) → home (balances, add/deduct) → kid
portfolio (holdings, since-purchase %, sell) → buy flow (units/amount
toggle with a live server-computed quote, snapped to a real tradable
step size) → per-kid history (general + investment-only, now currency-
and source-aware — see below) → settings (currency, kid management,
**real currency conversion with a warning dialog**). 65 backend tests
pass (`cd backend && pytest`), frontend `npm run build`/`npm run lint`
are clean.

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
