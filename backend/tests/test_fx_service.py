"""Pure logic — no DB needed for the table-based helpers."""

from decimal import Decimal

from app.services.fx_service import convert_from_table, rate_from_table


def test_same_currency_is_always_rate_one():
    assert rate_from_table({}, "USD", "USD") == Decimal("1")


def test_direct_pair_lookup():
    rates = {("USD", "ILS"): Decimal("3.5")}
    assert rate_from_table(rates, "USD", "ILS") == Decimal("3.5")


def test_falls_back_to_inverse_pair():
    rates = {("ILS", "USD"): Decimal("0.25")}
    assert rate_from_table(rates, "USD", "ILS") == Decimal("1") / Decimal("0.25")


def test_missing_pair_returns_none():
    assert rate_from_table({}, "USD", "EUR") is None


def test_convert_from_table_applies_rate():
    rates = {("USD", "ILS"): Decimal("3.5")}
    assert convert_from_table(rates, Decimal("10"), "USD", "ILS") == Decimal("35.0")


def test_convert_from_table_missing_rate_returns_none():
    assert convert_from_table({}, Decimal("10"), "USD", "GBP") is None
