"""Cash-flow analytics behaviour for security deposit movements."""

from datetime import date
from decimal import Decimal

import pytest

from rentals.analytics.cash_flow import expense_drivers, portfolio_cash_flow
from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.services.deposits import create_movement
from rentals.tests.factories import (
    FXFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)

pytestmark = pytest.mark.django_db

D = date.fromisoformat


def filters_for(start, end, grain=Grain.MONTH, property_ids=()):
    return AnalyticsFilters(
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        grain=grain,
        currency="USD",
        comparison=None,
        property_ids=property_ids,
    )


@pytest.fixture
def tenant(sample_property):
    return TenantFactory(property=sample_property, lease_start=date(2025, 1, 1))


def move(tenant, kind, amount, d, currency="USD", **kw):
    return create_movement(
        tenant, date=D(d), kind=kind, currency=currency, amount=Decimal(amount), **kw
    )


def test_cash_flow_shows_receipt_as_deposit_not_income(
    landlord_user, sample_property, tenant
):
    """A receipt is cash in but must not be reported as rent income."""
    TransactionFactory(
        property=sample_property, category="rent", amount=Decimal("1000.00"),
        date=D("2026-01-10"), currency="USD",
    )
    move(tenant, "received", "1500", "2026-01-05")

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-01", "2026-01-31"))

    point = result.points[0]
    assert point["rent"] == 1000.0
    assert point["total_income"] == 1000.0
    assert point["net_income"] == 1000.0
    assert point["deposits"] == 1500.0
    assert point["net_cash_flow"] == 2500.0
    assert [(s.key, s.kind) for s in result.series][-2:] == [
        ("deposits", "deposit_movement"),
        ("net_cash_flow", "net_cash"),
    ]


def test_cash_flow_application_nets_to_zero_cash(landlord_user, tenant):
    """Applying a deposit to rent adds rent income and removes the same from deposits."""
    move(tenant, "received", "1500", "2026-01-05")
    move(tenant, "applied", "1500", "2026-02-10", applied_to="rent")

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-01", "2026-02-28"))

    feb = result.points[1]
    assert feb["rent"] == 1500.0
    assert feb["deposits"] == -1500.0
    assert feb["net_cash_flow"] == 0.0


def test_cash_flow_attached_partial_application(
    landlord_user, sample_property, tenant
):
    """Applying part of a deposit to an existing row nets only that part."""
    move(tenant, "received", "1500", "2026-01-05")
    row = TransactionFactory(
        property=sample_property, tenant=tenant, category="rent",
        amount=Decimal("1500.00"), date=D("2026-03-05"), currency="USD",
    )
    move(tenant, "applied", "500", "2026-03-05", applied_to="rent", transaction=row)

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-01", "2026-03-31"))

    assert result.points[2]["net_cash_flow"] == 1000.0


def test_cash_flow_without_movements_has_no_deposit_keys(
    landlord_user, sample_property
):
    TransactionFactory(
        property=sample_property, category="rent", amount=Decimal("1000.00"),
        date=D("2026-01-10"), currency="USD",
    )

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-01", "2026-01-31"))

    assert "deposits" not in result.points[0]
    assert "net_cash_flow" not in result.points[0]
    assert [s.key for s in result.series] == [
        "rent", "total_income", "total_expenses", "net_income", "cumulative_net_income",
    ]


def test_cash_flow_excludes_deposits_of_unselected_property(
    landlord_user, sample_property, tenant
):
    other = PropertyFactory(owned_by=landlord_user.landlord)
    other_tenant = TenantFactory(property=other, lease_start=date(2025, 1, 1))
    move(other_tenant, "received", "900", "2026-01-05")

    result = portfolio_cash_flow(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31", property_ids=(sample_property.id,)),
    )

    assert all("deposits" not in p for p in result.points)
    assert "deposits" not in [s.key for s in result.series]


def test_cash_flow_converts_deposits_to_reporting_currency(landlord_user, tenant):
    FXFactory(
        from_currency="GBP", to_currency="USD", rate=Decimal("1.25"), date=D("2026-01-01")
    )
    move(tenant, "received", "1000", "2026-01-05", currency="GBP")

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-01", "2026-01-31"))

    assert result.points[0]["deposits"] == 1250.0
    assert result.points[0]["net_cash_flow"] == 1250.0


def test_cash_flow_counts_only_movements_inside_each_period(landlord_user, tenant):
    """Movements outside the filter range never leak into the first or last period."""
    move(tenant, "received", "1000", "2025-12-20")
    move(tenant, "received", "200", "2026-01-20")
    move(tenant, "returned", "100", "2026-02-20")

    result = portfolio_cash_flow(landlord_user, filters_for("2026-01-15", "2026-02-10"))

    assert [p["deposits"] for p in result.points] == [200.0, 0.0]


def test_expense_drivers_ignore_deposits(landlord_user, sample_property, tenant):
    TransactionFactory(
        property=sample_property, category="utilities", amount=Decimal("-300.00"),
        date=D("2026-01-12"), currency="USD",
    )
    move(tenant, "received", "1500", "2026-01-05")

    result = expense_drivers(landlord_user, filters_for("2026-01-01", "2026-01-31"))

    assert [s.key for s in result.series] == ["utilities"]
    assert result.points[0] == {
        "period_start": D("2026-01-01"),
        "period_end": D("2026-01-31"),
        "utilities": -300.0,
    }
