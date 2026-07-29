"""Behavior tests for the portfolio cash-flow analytics services."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.tests.factories import TransactionFactory


def filters_for(start, end, grain=Grain.MONTH):
    return AnalyticsFilters(
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        grain=grain,
        currency="USD",
        comparison=None,
        property_ids=(),
    )


@pytest.mark.django_db
def test_cash_flow_returns_raw_signed_values(landlord_user, sample_property):
    """Dropping signed amounts or cumulative net would corrupt cash-flow decisions."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("2000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("-300.00"),
        date=date(2026, 1, 12),
        currency="USD",
    )

    result = portfolio_cash_flow(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert result.scale == 1
    assert result.points == (
        {
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "rent": 2000.0,
            "utilities": -300.0,
            "total_income": 2000.0,
            "total_expenses": -300.0,
            "net_income": 1700.0,
            "cumulative_net_income": 1700.0,
        },
    )


@pytest.mark.django_db
def test_cash_flow_uses_calendar_quarter_boundaries(landlord_user, sample_property):
    """Changing period boundaries would place transactions in the wrong trend bucket."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("100.00"),
        date=date(2026, 3, 31),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("-25.00"),
        date=date(2026, 4, 1),
        currency="USD",
    )

    result = portfolio_cash_flow(
        landlord_user,
        filters_for("2026-02-10", "2026-05-20", Grain.QUARTER),
    )

    assert result.points == (
        {
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "rent": 100.0,
            "utilities": 0.0,
            "total_income": 100.0,
            "total_expenses": 0.0,
            "net_income": 100.0,
            "cumulative_net_income": 100.0,
        },
        {
            "period_start": date(2026, 4, 1),
            "period_end": date(2026, 6, 30),
            "rent": 0.0,
            "utilities": -25.0,
            "total_income": 0.0,
            "total_expenses": -25.0,
            "net_income": -25.0,
            "cumulative_net_income": 75.0,
        },
    )


@pytest.mark.django_db
def test_expense_drivers_exclude_income_and_define_expense_kind(
    landlord_user, sample_property
):
    """Classifying categories in the client would make expense drivers inconsistent."""
    from rentals.analytics.cash_flow import expense_drivers

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("2000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("-300.00"),
        date=date(2026, 1, 12),
        currency="USD",
    )

    result = expense_drivers(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert [(series.key, series.kind) for series in result.series] == [
        ("utilities", "expense")
    ]
    assert result.points == (
        {
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "utilities": -300.0,
        },
    )


@pytest.mark.django_db
def test_cash_flow_query_count_does_not_grow_with_period_count(
    landlord_user, sample_property
):
    """Querying once per calendar bucket would make long ranges increasingly slow."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    for month in range(1, 13):
        TransactionFactory(
            property=sample_property,
            category="rent",
            amount=Decimal("100.00"),
            date=date(2026, month, 1),
            currency="USD",
        )

    with CaptureQueriesContext(connection) as queries:
        result = portfolio_cash_flow(
            landlord_user, filters_for("2026-01-01", "2026-12-31")
        )

    assert len(result.points) == 12
    assert len(queries) <= 1
