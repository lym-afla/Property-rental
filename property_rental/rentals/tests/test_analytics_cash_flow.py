"""Behavior tests for the portfolio cash-flow analytics services."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.tests.factories import FXFactory, TransactionFactory


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
    assert [(series.key, series.kind) for series in result.series] == [
        ("rent", "income_category"),
        ("utilities", "expense_category"),
        ("total_income", "income_total"),
        ("total_expenses", "expense_total"),
        ("net_income", "net"),
        ("cumulative_net_income", "cumulative"),
    ]
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
def test_cash_flow_normalizes_legacy_positive_expenses_to_negative(
    landlord_user, sample_property
):
    """Passing through legacy-positive expenses would overstate portfolio net income."""
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
        amount=Decimal("300.00"),
        date=date(2026, 1, 12),
        currency="USD",
    )

    result = portfolio_cash_flow(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert result.points[0]["utilities"] == -300.0
    assert result.points[0]["total_expenses"] == -300.0
    assert result.points[0]["net_income"] == 1700.0


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
            "period_start": date(2026, 2, 10),
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
            "period_end": date(2026, 5, 20),
            "rent": 0.0,
            "utilities": -25.0,
            "total_income": 0.0,
            "total_expenses": -25.0,
            "net_income": -25.0,
            "cumulative_net_income": 75.0,
        },
    )


def test_cash_flow_clamps_partial_bucket_boundaries_to_requested_range(
    landlord_user, sample_property
):
    """Returning full calendar bounds would drill into transactions outside the bar."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    result = portfolio_cash_flow(
        landlord_user,
        filters_for("2026-01-15", "2026-02-10"),
    )

    assert [
        (point["period_start"], point["period_end"]) for point in result.points
    ] == [
        (date(2026, 1, 15), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 10)),
    ]


def test_cash_flow_safely_terminates_a_bucket_at_date_max(landlord_user):
    """Always constructing the next year would crash a valid year-9999 request."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    result = portfolio_cash_flow(
        landlord_user,
        filters_for("9999-12-31", "9999-12-31"),
    )

    assert len(result.points) == 1
    assert result.points[0]["period_start"] == date.max
    assert result.points[0]["period_end"] == date.max


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
        ("utilities", "expense_category")
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


@pytest.mark.django_db
def test_cash_flow_preloads_cross_currency_rates_for_long_ranges(
    landlord_user, sample_property
):
    """Per-transaction FX lookups would make a long cross-currency trend N+1."""
    from rentals.analytics.cash_flow import portfolio_cash_flow

    FXFactory(
        from_currency="GBP",
        to_currency="USD",
        rate=Decimal("1.25"),
        date=date(2026, 1, 1),
    )
    for month in range(1, 13):
        TransactionFactory(
            property=sample_property,
            category="rent",
            amount=Decimal("100.00"),
            date=date(2026, month, 1),
            currency="GBP",
        )

    with CaptureQueriesContext(connection) as queries:
        result = portfolio_cash_flow(
            landlord_user, filters_for("2026-01-01", "2026-12-31")
        )

    assert len(result.points) == 12
    assert result.points[0]["rent"] == 125.0
    assert result.points[-1]["rent"] == 125.0
    assert len(queries) <= 2


@pytest.mark.django_db
def test_preloaded_converter_matches_legacy_equal_hop_path_selection(
    landlord_user, sample_property
):
    """Reordering FX rows must not choose a different equal-hop conversion path."""
    from rentals.services import fx as fx_service
    from rentals.services.fx import preload_converter

    # The legacy graph receives the RUB path first through natural ORM order,
    # even though the EUR path's rows carry earlier dates. Both paths are two
    # hops, but their rates intentionally produce different GBP->USD values.
    FXFactory(
        from_currency="GBP",
        to_currency="RUB",
        rate=Decimal("4.00"),
        date=date(2026, 1, 2),
    )
    FXFactory(
        from_currency="RUB",
        to_currency="USD",
        rate=Decimal("5.00"),
        date=date(2026, 1, 2),
    )
    FXFactory(
        from_currency="GBP",
        to_currency="EUR",
        rate=Decimal("2.00"),
        date=date(2026, 1, 1),
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("3.00"),
        date=date(2026, 1, 1),
    )
    transaction = TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("100.00"),
        date=date(2026, 1, 3),
        currency="GBP",
    )

    legacy_value = fx_service.convert(
        transaction.amount, transaction.currency, "USD", transaction.date
    )
    preloaded_value = preload_converter([transaction], "USD").convert(
        transaction.amount, transaction.currency, "USD", transaction.date
    )

    assert legacy_value == Decimal("2000.00")
    assert preloaded_value == legacy_value
