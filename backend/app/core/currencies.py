"""Single source of truth for the currencies the app offers in the
Settings currency picker (mirrored in frontend/src/lib/currencies.ts —
keep both lists in sync if you touch either). The scheduler uses this
list to keep an FX rate warm for every one of them, not just the ones
already in use, so switching to a currency nobody's picked yet doesn't
leave the family without a resolvable rate.
"""

SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "ILS", "CAD", "AUD", "CHF", "JPY"]
