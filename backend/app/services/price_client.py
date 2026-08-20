"""Thin client over Yahoo Finance's chart endpoint.

Isolated behind this module per architecture 5.2 ("Price fetching routed
through a client abstraction layer so the provider can be swapped without
touching service logic") and only ever called by the scheduler, never
per-request (spec 4.3).
"""

from datetime import datetime, timezone

import httpx

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Kept short: only enough lookback for the buy-screen sparkline (spec 2.4
# keeps the historical chart in native currency and deliberately simple).
CHART_PARAMS = {"range": "1mo", "interval": "1d"}

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FamilyBankScheduler/1.0)"}


class PriceFetchError(RuntimeError):
    pass


async def fetch_quote(client: httpx.AsyncClient, symbol: str) -> dict:
    """Returns {"price": float, "currency": str, "history": [{"date","close"}]}."""
    resp = await client.get(
        CHART_URL.format(symbol=symbol), params=CHART_PARAMS, headers=_HEADERS, timeout=15.0
    )
    resp.raise_for_status()
    data = resp.json()

    result = data.get("chart", {}).get("result")
    if not result:
        raise PriceFetchError(f"No chart result for {symbol}: {data.get('chart', {}).get('error')}")

    payload = result[0]
    meta = payload["meta"]
    timestamps = payload.get("timestamp", [])
    closes = payload["indicators"]["quote"][0].get("close", [])

    history = [
        {"date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"), "close": round(close, 4)}
        for ts, close in zip(timestamps, closes)
        if close is not None
    ]

    price = meta.get("regularMarketPrice")
    if price is None:
        raise PriceFetchError(f"No regularMarketPrice for {symbol}")

    return {
        "price": float(price),
        "currency": meta.get("currency", "USD"),
        "history": history,
    }
