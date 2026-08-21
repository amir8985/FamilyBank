from decimal import Decimal

from app.models.debt_transaction import DebtTransactionType
from app.models.family import Family
from app.models.kid import Kid
from app.services import debts_db_service


async def _make_kid(db_session, family: Family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def test_balance_starts_at_zero(db_session, family):
    kid = await _make_kid(db_session, family)
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("0")


async def test_add_and_deduct_nets_correctly(db_session, family):
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("50"))
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("30"))
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.DEDUCT, Decimal("20"))
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("60")


async def test_balance_can_go_negative(db_session, family):
    # The service layer doesn't forbid this itself — routes/UI decide
    # whether to allow it. Confirms the raw ledger math has no floor.
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.DEDUCT, Decimal("10"))
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("-10")


async def test_get_balances_batches_multiple_kids(db_session, family):
    kid_a = await _make_kid(db_session, family, "A")
    kid_b = await _make_kid(db_session, family, "B")
    kid_c_no_transactions = await _make_kid(db_session, family, "C")

    await debts_db_service.record_transaction(db_session, kid_a.id, DebtTransactionType.ADD, Decimal("100"))
    await debts_db_service.record_transaction(db_session, kid_b.id, DebtTransactionType.ADD, Decimal("5"))
    await debts_db_service.record_transaction(db_session, kid_b.id, DebtTransactionType.DEDUCT, Decimal("2"))

    balances = await debts_db_service.get_balances(
        db_session, [kid_a.id, kid_b.id, kid_c_no_transactions.id]
    )
    assert balances[kid_a.id] == Decimal("100")
    assert balances[kid_b.id] == Decimal("3")
    assert balances[kid_c_no_transactions.id] == Decimal("0")


async def test_get_balances_empty_list_returns_empty_dict(db_session):
    assert await debts_db_service.get_balances(db_session, []) == {}


async def test_list_transactions_returns_both_with_notes(db_session, family):
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(
        db_session, kid.id, DebtTransactionType.ADD, Decimal("1"), note="first"
    )
    await debts_db_service.record_transaction(
        db_session, kid.id, DebtTransactionType.ADD, Decimal("2"), note="second"
    )
    rows = await debts_db_service.list_transactions(db_session, kid.id)
    assert {r.note for r in rows} == {"first", "second"}


async def test_record_transaction_defaults_to_not_an_adjustment(db_session, family):
    # is_adjustment is only ever True for the currency-conversion row
    # apply_currency_conversion writes (see test_currency_change.py) —
    # a normal parent-entered add/deduct must default to False.
    kid = await _make_kid(db_session, family)
    txn = await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("5"))
    assert txn.is_adjustment is False
