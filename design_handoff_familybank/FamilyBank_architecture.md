# FamilyBank — Architecture (v1)

Companion doc to `spec_en.md`. This covers only what's needed to build v1
(parent-only, free, single currency setting per family, Yahoo price feed).
v2 items (kid login, co-parent, fixed allowance rules, per-viewer display
currency) are called out but not designed in depth yet.

---

## 1. Data model

Single Postgres database, multi-tenant via `family_id` on every
family-scoped table. No per-tenant databases.

```sql
-- Tenant root
families (
  id, base_currency, created_at
)

-- Auth
users (
  id, family_id, email, password_hash / oauth_id, created_at
)

kids (
  id, family_id, name, avatar, created_at
)

-- Existing ledger (port as-is)
debt_transactions (
  id, kid_id, amount, note, type[add/deduct], created_at
)

-- Investing (port as-is, + currency field)
investment_holdings (
  id, kid_id, symbol, units, avg_cost, avg_cost_currency, created_at, updated_at
)

investment_transactions (
  id, kid_id, symbol, units, price, price_currency, type[buy/sell], created_at
)

-- Global (NOT per-family — shared read-only reference data)
asset_catalog (
  symbol, display_name, kind[stock/basket], description
)

price_cache (
  symbol, price, currency, updated_at, history_json
)

fx_rates_cache (
  base_currency, quote_currency, rate, updated_at
)
```

**Currency storage principle:** amounts are stored tagged with the
currency they were priced in at the time (`price_currency`,
`avg_cost_currency`), not pre-converted into the family's base currency.
Conversion to the family's `base_currency` happens **at read time**, in
the API layer, using whatever the latest `fx_rates_cache` entry is. This
is what makes "family changes their base currency" a zero-migration
operation, and leaves room for a v2 per-viewer display currency without
touching stored data at all.

---

## 2. Backend services

Same shape as the existing `app/agents/investing/` module, extended:

```
app/agents/investing/
  client.py         -- Yahoo Finance chart endpoint calls (unchanged from v0)
  cache.py           -- reads/writes price_cache
  fx.py               -- NEW: fetches + caches fx_rates_cache
  scheduler.py        -- extended: pulls prices AND fx rates in the same run
  investing_service.py -- extended: family_id scoping, converts at read time
                          via fx.py, wraps buy()/sell() in db.transaction()
```

`debts_db_service.py` gets the same `family_id` scoping treatment.

**Scheduler cadence:** one job, 4-5 runs/day, each run:
1. Pull latest price + today's history for every symbol in `asset_catalog`
2. Pull latest FX rate for every currency pair actually in use (USD, ILS,
   EUR → whatever base currencies exist across families)
3. Write both into their respective caches with the same `updated_at`

This keeps the "prices updated at 12:47 PM" timestamp in the UI accurate
for FX too, and means adding a new family with a new base currency just
means adding one more pair to step 2 — no new job.

**Transaction integrity:** `buy()`/`sell()` now wrap the cash-debit +
holdings-write + transaction-log write in `db.transaction()` — worth
closing this gap now that it's a public multi-tenant app rather than one
family's data.

---

## 3. API layer

Family-scoped middleware: every authenticated request resolves
`family_id` from the session and every downstream DB call is required to
pass it explicitly (no "trust the client" scoping) — this is the main
thing to stress-test in review, since it's the one bug class that leaks
one family's data into another's.

Endpoints stay close to the existing shape (`GET /kids/:id/portfolio`,
`POST /kids/:id/buy`, `POST /kids/:id/sell`, `GET /kids/:id/debt`,
`POST /kids/:id/debt`), with responses carrying already-converted amounts
in the family's `base_currency` (chart series stay in native currency per
the spec's 4.2 decision).

---

## 4. Frontend

Next.js, same screen structure as the existing screenshots (My
Investments / Buy tabs, symbol detail modal, Kids Balances panel).

**PWA setup:**
- `manifest.json` (name, icons, theme color, `display: standalone`)
- Service worker (via `next-pwa` or manual) for installability + basic
  offline shell — not for offline trading, just so "Add to Home Screen"
  works cleanly on iOS/Android
- No native app / app store submission needed for v1

**Auth:** NextAuth, email+password or Google OAuth, parent-only sessions
for v1.

---

## 5. Hosting & ops (v1, free-tier friendly)

- **App:** Vercel or Railway (Next.js + API routes/serverless functions)
- **DB:** managed Postgres — Supabase or Neon (both have workable free
  tiers for early scale)
- **Scheduler:** a scheduled function (Vercel Cron / Railway Cron) hitting
  an internal endpoint 4-5x/day, rather than a long-running worker process
  — simplest thing that works at this scale
- **No billing infra** — confirmed not needed while the product is free

---

## 6. What's explicitly out of scope for v1
- Kid login / kid-initiated trades (v2)
- Co-parent accounts (v2)
- Recurring/fixed allowance rules (v2)
- Per-viewer display currency preference (v2 — but storage is already
  designed to support it without migration, see section 1)
- Children's-data privacy policy — **not skipped, just sequenced**: flagged
  to revisit specifically before public launch, not before starting to
  build
- Swapping the Yahoo price source — revisit only if it breaks in practice
