"""Regression coverage for the FX-conversion consolidation done in
Plan B Tasks 2 & 3.

The characterization tests in ``test_financials_char.py`` pin the
end-to-end outputs of ``Transaction.financials`` and ``pnl_calc`` byte-
for-byte. They pass through ``services.financials.convert_transactions``
under the hood (Task 2 wired ``aggregate`` to it; Task 3 wired the two
``pnl_calc`` FX loops under the ``default_currency_for_all_data=True``
branch to it), but a char test only fails when the OUTPUT drifts — a
silent refactor that breaks ``convert_transactions`` in a path the char
scenario doesn't exercise would slip through.

This module fills that gap with five focused unit tests on
``convert_transactions`` and the ``pnl_calc`` ``True`` branch directly:

1. ``test_convert_transactions_same_currency_short_circuits`` — when
   every row already matches the target currency, no FX lookup happens.
   Pins the ``services.fx.convert`` short-circuit (Task 2 invariant).
2. ``test_convert_transactions_single_cross_currency`` — one GBP row
   converted to USD picks up the stored rate. Pins the post-FX-fix
   arithmetic (Plan B Task 1: stored rate, not its reciprocal).
3. ``test_convert_transactions_multi_row_aggregation`` — mixed-currency
   rows aggregate to a single Decimal. Pins the loop accumulation.
4. ``test_convert_transactions_empty_list_returns_zero`` — empty
   iterable returns ``int`` 0 (matches the ``total = 0`` initializer
   the old inline loops used; ``aggregate`` relies on this for the
   "no rows in range" case).
5. ``test_pnl_calc_cross_currency_true_branch`` — directly exercises
   ``pnl_calc(default_currency_for_all_data=True)``. The existing char
   test only covers the ``False`` branch; production hard-codes ``True``
   so the ``True`` branch (the path that actually calls
   ``convert_transactions``) had no direct coverage. This closes that
   gap: a GBP rent transaction is converted to USD at the stored rate
   and lands in ``rent_ytd`` converted, not face-value.
"""

import pytest
from datetime import date
from decimal import Decimal

from rentals.services.financials import convert_transactions
from rentals.tests.factories import (
    PropertyFactory,
    TransactionFactory,
    FXFactory,
    LandlordFactory,
    TenantFactory,
)


@pytest.mark.django_db
def test_convert_transactions_same_currency_short_circuits(db):
    """When all transactions match target currency, no FX lookup happens."""
    property = PropertyFactory(currency="USD")
    txns = [
        TransactionFactory(
            property=property,
            amount=Decimal("100.00"),
            currency="USD",
            date=date(2024, 1, 15),
        ),
        TransactionFactory(
            property=property,
            amount=Decimal("200.00"),
            currency="USD",
            date=date(2024, 1, 15),
        ),
    ]
    total = convert_transactions(txns, "USD", date(2024, 6, 1))
    assert total == Decimal("300.00")


@pytest.mark.django_db
def test_convert_transactions_single_cross_currency(db):
    """A single GBP transaction converted to USD uses the FX rate."""
    property = PropertyFactory(currency="GBP")
    FXFactory(
        date=date(2024, 1, 1),
        from_currency="GBP",
        to_currency="USD",
        rate=Decimal("1.25"),
    )
    txns = [
        TransactionFactory(
            property=property,
            amount=Decimal("100.00"),
            currency="GBP",
            date=date(2024, 1, 15),
        )
    ]
    total = convert_transactions(txns, "USD", date(2024, 6, 1))
    # 100 GBP * 1.25 (stored rate, post-FX-fix: actual rate, not reciprocal)
    assert total == Decimal("125.00")


@pytest.mark.django_db
def test_convert_transactions_multi_row_aggregation(db):
    """Multiple transactions in mixed currencies aggregate correctly."""
    property = PropertyFactory(currency="USD")
    FXFactory(
        date=date(2024, 1, 1),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.10"),
    )
    txns = [
        TransactionFactory(
            property=property,
            amount=Decimal("100.00"),
            currency="USD",
            date=date(2024, 1, 15),
        ),
        TransactionFactory(
            property=property,
            amount=Decimal("100.00"),
            currency="EUR",
            date=date(2024, 1, 15),
        ),
    ]
    total = convert_transactions(txns, "USD", date(2024, 6, 1))
    # 100 USD (passthrough) + 100 EUR * 1.10 = 100 + 110 = 210
    assert total == Decimal("210.00")


@pytest.mark.django_db
def test_convert_transactions_empty_list_returns_zero(db):
    """An empty iterable returns ``int`` 0 (matches the old loop
    initializer that ``aggregate`` relies on for the no-rows case)."""
    total = convert_transactions([], "USD", date(2024, 6, 1))
    assert total == 0


@pytest.mark.django_db
def test_pnl_calc_cross_currency_true_branch(db):
    """Directly exercise ``pnl_calc``'s ``default_currency_for_all_data=True``
    branch (the refactored path using ``convert_transactions``).

    Production passes ``True`` hard-coded; the existing char test
    (``test_pnl_calc_portfolio``) only covers the ``False`` branch, so
    the ``True`` branch — the only one that actually calls
    ``convert_transactions`` — had no direct coverage. This closes that
    gap: a GBP rent transaction is converted to USD via the stored rate
    and ``rent_ytd`` reflects the converted amount (1250), not the
    face-value amount (1000).
    """
    from rentals.services.financials import pnl_calc

    landlord = LandlordFactory()
    property = PropertyFactory(owned_by=landlord, currency="GBP")
    tenant = TenantFactory(property=property)
    FXFactory(
        date=date(2024, 1, 1),
        from_currency="GBP",
        to_currency="USD",
        rate=Decimal("1.25"),
    )
    # GBP rent transaction that will be converted to USD inside pnl_calc.
    TransactionFactory(
        property=property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1000.00"),
        currency="GBP",
        date=date(2024, 1, 15),
        period="2024-01",
    )

    expenses, rent_ytd, rent_all_time, unique_categories = pnl_calc(
        [property], "USD", True, 0, as_of=date(2024, 6, 1)
    )
    # 1000 GBP * 1.25 = 1250 USD. Cross-currency conversion happened iff
    # rent_ytd is NOT the face-value 1000.
    assert rent_ytd != Decimal("1000"), (
        f"rent_ytd was face-value ({rent_ytd!r}); cross-currency "
        "conversion did NOT happen — True branch broken."
    )
    assert rent_ytd == Decimal("1250") or float(rent_ytd) == 1250.0, (
        f"rent_ytd={rent_ytd!r}, expected 1250 (1000 GBP * 1.25 USD/GBP)"
    )
