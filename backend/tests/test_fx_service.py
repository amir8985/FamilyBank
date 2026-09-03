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


def test_triangulates_through_usd_when_no_direct_pair_cached():
    # Only USD legs cached (what the scheduler actually caches), no
    # direct EUR<->ILS pair — must still resolve via USD. Both legs here
    # are the *inverse* of what's cached (USD->EUR, USD->ILS), so
    # EUR->ILS = (1/0.9) * 3.6.
    rates = {("USD", "EUR"): Decimal("0.9"), ("USD", "ILS"): Decimal("3.6")}
    expected = (Decimal("1") / Decimal("0.9")) * Decimal("3.6")
    assert rate_from_table(rates, "EUR", "ILS") == expected


def test_triangulation_also_works_through_direct_usd_legs():
    # Here EUR->USD is cached directly (not as an inverse), so
    # EUR->ILS = 1.1 * 3.6.
    rates = {("EUR", "USD"): Decimal("1.1"), ("USD", "ILS"): Decimal("3.6")}
    assert rate_from_table(rates, "EUR", "ILS") == Decimal("1.1") * Decimal("3.6")


def test_triangulation_returns_none_if_either_usd_leg_missing():
    assert rate_from_table({("USD", "EUR"): Decimal("0.9")}, "EUR", "ILS") is None
