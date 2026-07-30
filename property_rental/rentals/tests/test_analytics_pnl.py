"""Tests for the shared annual and year-to-date P&L service."""

from datetime import date
from decimal import Decimal

import pytest

from rentals.analytics.pnl import profit_and_loss
from rentals.tests.factories import FXFactory, PropertyFactory, TransactionFactory


def _row(result, key):
    return next(row for row in result.rows if row.key == key)


@pytest.fixture
def pnl_transactions(landlord_user):
    property_a = PropertyFactory(owned_by=landlord_user.landlord, name="Alpha")
    property_b = PropertyFactory(owned_by=landlord_user.landlord, name="Bravo")

    TransactionFactory(
        property=property_a,
        category="capex",
        amount=Decimal("-5000.00"),
        currency="USD",
        date=date(2023, 6, 1),
    )
    TransactionFactory(
        property=property_a,
        category="rent",
        amount=Decimal("12000.00"),
        currency="USD",
        date=date(2024, 3, 1),
    )
    TransactionFactory(
        property=property_a,
        category="tax",
        amount=Decimal("-2000.00"),
        currency="USD",
        date=date(2024, 4, 1),
    )
    TransactionFactory(
        property=property_b,
        category="rent",
        amount=Decimal("10000.00"),
        currency="EUR",
        date=date(2024, 5, 1),
    )
    FXFactory(
        date=date(2024, 5, 1),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.20"),
    )
    TransactionFactory(
        property=property_a,
        category="rent",
        amount=Decimal("7000.00"),
        currency="USD",
        date=date(2025, 2, 1),
    )
    TransactionFactory(
        property=property_b,
        category="management",
        amount=Decimal("-500.00"),
        currency="USD",
        date=date(2025, 7, 1),
    )
    TransactionFactory(
        property=property_a,
        category="rent",
        amount=Decimal("9999.00"),
        currency="USD",
        date=date(2025, 9, 1),
    )
    return property_a, property_b


@pytest.mark.django_db
def test_profit_and_loss_builds_reconciling_annual_and_ytd_columns(
    landlord_user, pnl_transactions
):
    """Wrong periods, category signs, FX dates, or totals break the statement."""
    result = profit_and_loss(
        landlord_user,
        end=date(2025, 7, 30),
        currency="USD",
    )

    assert [column.key for column in result.columns] == [
        "2023",
        "2024",
        "2025",
        "ytd",
    ]
    assert result.columns[-1].key == "ytd"
    assert result.columns[-1].start == date(2025, 1, 1)
    assert result.columns[-1].end == date(2025, 7, 30)
    assert result.rows_by_key["rent"].values["2024"] == pytest.approx(24_000)
    assert result.rows_by_key["tax"].values["2024"] == pytest.approx(-2_000)
    assert result.rows_by_key["rent"].values["2023"] == 0
    assert result.total_revenue["2024"] + result.total_expenses[
        "2024"
    ] == pytest.approx(result.net_income["2024"])
    assert result.rows_by_key["rent"].values["2025"] == pytest.approx(7_000)
    assert result.rows_by_key["rent"].values["ytd"] == pytest.approx(7_000)
    assert [row.key for row in result.rows] == [
        "rent",
        "tax",
        "capex",
        "management",
        "total_revenue",
        "total_expenses",
        "net_income",
    ]


@pytest.mark.django_db
def test_profit_and_loss_property_scope_excludes_other_owned_properties(
    landlord_user, pnl_transactions
):
    """Ignoring property_ids would make property statements include portfolio data."""
    property_a, _property_b = pnl_transactions

    result = profit_and_loss(
        landlord_user,
        end=date(2025, 7, 30),
        currency="USD",
        property_ids=(property_a.id,),
    )

    assert result.rows_by_key["rent"].values["2024"] == pytest.approx(12_000)
    assert "management" not in result.rows_by_key
    for key in ("2023", "2024", "2025", "ytd"):
        assert result.total_revenue[key] + result.total_expenses[
            key
        ] == pytest.approx(result.net_income[key])


@pytest.mark.django_db
def test_profit_and_loss_ignores_unowned_requested_properties(
    landlord_user, other_landlord_user
):
    """A caller-supplied foreign property id must never bypass owner scoping."""
    own_property = PropertyFactory(owned_by=landlord_user.landlord)
    foreign_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    TransactionFactory(
        property=own_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2025, 1, 1),
    )
    TransactionFactory(
        property=foreign_property,
        category="rent",
        amount=Decimal("9000.00"),
        date=date(2025, 1, 1),
    )

    result = profit_and_loss(
        landlord_user,
        end=date(2025, 7, 30),
        currency="USD",
        property_ids=(own_property.id, foreign_property.id),
    )

    assert _row(result, "rent").values["2025"] == pytest.approx(1000)
