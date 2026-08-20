# FamilyBank — Product Spec

## 0. Summary
An app for parents to track how much they owe their kids (allowance/debt
ledger), with a feature letting kids "invest" that balance in real stocks
and indices, at real market prices — but **the money itself stays fully
virtual**: no broker, no real money movement, no real securities purchase.
The parent decides how much they "owe" the kid; that balance is what drives
the whole game.

This distinction has to stay sharp on every screen: **"this is an
educational game using real prices, not real trading."** That framing (both
in onboarding copy and in the Terms) is also what keeps this a normal
educational app legally, instead of a regulated fintech product (licensing,
KYC, liability for holding customer funds).

---

## 1. Users & Roles

| Role | Permissions |
|---|---|
| **Parent (Owner)** | Creates the family, adds/removes kids, adds/reduces debt, sees everything, can buy/sell on a kid's behalf or grant the kid permission to act independently |
| **Co-parent** | Same permissions as Owner within the same family — **deferred to v2** |
| **Kid** | **v1:** no login, viewed only through the parent's screen. **v2:** gets their own access, can trade (buy/sell) but explicitly cannot add money to their own balance — only a parent can do that |

**v1:** one parent per family, multiple kids, kids don't log in at all —
everything happens through the parent's screen (same as the original
handoff).
**v2 roadmap (confirmed, not building yet):** kid-facing login/access
(trade-only, no self-funding), co-parent accounts, recurring/fixed
allowance ("קבוע") rules.

---

## 2. Core Flows

### 2.1 Signup & family setup
1. Parent signs up (email+password or Google OAuth)
2. Chooses the family's **base currency** (₪ / € / $ ...).
   **v1:** one currency setting per family, changeable anytime in settings
   (not locked in forever — just a single value, not per-kid or
   per-viewer yet).
   **v2 idea to keep in mind while designing storage:** let each *viewer*
   (parent vs. kid, or even each parent) see amounts in their own
   preferred display currency, independent of what's stored. This is why
   the architecture (section 5) stores amounts in a currency-agnostic way
   and converts only at display time — so v2 personal display-currency
   preferences are a UI-layer addition, not a data migration.
3. Adds kids (name, maybe avatar/color like in the screenshots provided)

### 2.2 Debt / allowance management
Essentially identical to the "Kids Balances" screen you shared: add to
debt, deduct/pay, free-text note, transaction history. This already exists
and works — near-direct port.

### 2.3 Investing
1. Kid or parent enters a specific kid's "Investments" screen
2. Tab "My Investments" (default) / tab "Buy"
3. Pick a stock/basket → detail screen (chart, daily change, kid-friendly
   description)
4. Buy: enter units **or** an amount in the home currency → show
   "will actually cost X€" before confirming
5. Sell: only available from the portfolio, only against an existing
   holding
6. Every action creates a record in `investment_transactions` and a
   matching row in the general transaction history (debt goes up/down
   accordingly)

### 2.4 Currency conversion (the key difference from the original version)
In the original version this was a deliberate 1:1 fake. Now it needs to be
real:
- Raw price comes back from Yahoo/the price provider in its native
  currency (USD/ILS/EUR)
- An exchange rate converts it to the family's home currency. **Refreshed
  on the same cycle as prices (4-5x/day), not a separate daily job** — one
  scheduler pass pulls both stock prices and FX rates together
- Display is always in the home currency — the kid never needs to know
  AAPL is priced in dollars
- **Decision: keep the historical chart simple.** Converting every
  historical point with its own historical FX rate adds real complexity
  for a cosmetic detail. Instead, the lookback chart shows the price in
  its **original currency** (with the currency noted, e.g. "in $"), and
  only the live/current price + buy/sell amounts are converted to the
  home currency. Revisit only if this turns out to actually confuse kids.

---

## 3. Asset Catalog
Stays like the original — 20 kid-recognizable stocks + 5 baskets (including
TA35.TA and ^STOXX as real indices, not ETF proxies). For the public
version it's worth considering a catalog that adapts by the family's
country (e.g. TA35.TA ranked higher for a family in Israel), but that's a
v2 optimization, not MVP.

---

## 4. Decisions (resolved)

### 4.1 Independent kid action — RESOLVED
**v1: parent-only access, no kid login at all.**
**v2: kids get their own access, trade-only** (buy/sell within their
existing balance) — a kid can never add money to their own balance; only a
parent action can increase it.

### 4.2 Age / privacy considerations — FLAGGED FOR PRE-LAUNCH
No action needed now. **Reminder set: revisit this explicitly before public
launch** — a children's-data privacy policy is still required even without
real money involved, once this is public and collecting data about minors.

### 4.3 Price data source at public scale — RESOLVED, keep Yahoo for v1
Clarifying the design: **families never call the price API directly.**
Only our own scheduler does — 4-5 times a day, for the ~25 symbols in the
catalog, regardless of how many families or users are reading from the
cache. That's a genuinely small, constant number of outbound requests no
matter how big the user base gets, so the earlier scale concern doesn't
really apply here. **Decision: keep the Yahoo endpoint for v1**, since the
architecture already isolates it behind one central cache. Revisit only if
it actually starts failing/blocking in practice — not worth pre-optimizing
for a provider swap that may never be needed.

### 4.4 Business model — RESOLVED
**Fully free for now.** No billing/Stripe layer in the MVP architecture.

---

## 5. Architecture

### 5.1 Core principle: Multi-tenancy
A single Postgres DB, every table carries a `family_id` (except global
tables like the asset catalog and prices). Every query in the service
layer is filtered by the logged-in user's `family_id` — not a separate DB
per customer. This also means one migration for everyone, one backup, one
monitoring setup.

```
families                  (id, base_currency, created_at)
users                      (id, family_id, email, role, ...)      -- parents
kids                       (id, family_id, name, avatar, ...)
debt_transactions          (id, kid_id, amount, note, type, created_at)   -- already exists
investment_holdings        (id, kid_id, symbol, units, avg_cost, ...)
investment_transactions    (id, kid_id, symbol, units, price, type, created_at)

-- global, not per-family:
asset_catalog              (symbol, display_name, kind[stock/basket], description)
price_cache                (symbol, price, currency, updated_at, history_json)
fx_rates_cache              (base, quote, rate, date)
```

### 5.2 Backend
A Python service shaped exactly like the existing `investing_service.py`,
with:
- `family_id` scoping added to every query
- Price fetching routed through a client abstraction layer (so the
  provider can be swapped without touching service logic)
- A new FX layer: `fx_service.py` that fetches exchange rates (daily,
  cached) and converts every price before it leaves the API toward the
  frontend
- `db.transaction()` — the documented gap from the original version
  (non-atomic writes) is worth closing now that this is real users' money
  (even if virtual), not just one family that can tolerate a rare bug

### 5.3 Scheduler
One global job (cron / APScheduler / Celery beat) running 4-5 times a day,
refreshing `price_cache` and `fx_rates_cache` for every symbol in the
catalog **once** — not per-family — every family reads from the same
cache. This also solves the rate-limit concern from section 4.3.

### 5.4 Frontend
Next.js (same as the original project), with `next-pwa` / a manifest.json
+ service worker to support "Add to Home Screen." Auth via NextAuth
(email/Google). Screen structure stays very close to what already exists
in the screenshots you shared — that UI is already proven.

### 5.5 Auth & multi-family isolation
Every API request goes through middleware that pulls `family_id` from the
session and injects it into every DB-layer query — so there's no risk of
one family's data leaking into another's view (critical to check in code
review, not just the happy path).

### 5.6 Hosting
Vercel/Railway/Render for frontend+backend, managed Postgres (Supabase/
Neon/RDS) — all of these support the multi-tenant family_id model well;
no "database per tenant" infrastructure is needed.

---

## 6. What carries over almost 1:1 from the original project
- All the UX described in the handoff (tabs, live "will actually cost"
  preview, chart starting from first purchase, buy-only/sell-only
  separation) — all of it still applies here
- The holdings/transactions table structure
- `_unit_step_for_price` (finer units for expensive stocks)
- The `useSearchParams` + Suspense back-navigation pattern
