"""Behavior and API tests for portfolio performance analytics."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.tests.factories import (
    FXFactory,
    PropertyCapitalStructureFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)


def filters_for(start, end, grain=Grain.MONTH, property_ids=()):
    return AnalyticsFilters(
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        grain=grain,
        currency="USD",
        comparison=None,
        property_ids=tuple(property_ids),
    )


@pytest.mark.django_db
def test_two_overlapping_tenants_in_one_property_count_as_one_occupied_unit(
    landlord_user, sample_property
):
    """Counting tenants instead of properties would push occupancy above 100%."""
    from rentals.analytics.portfolio import portfolio_occupancy

    TenantFactory(
        property=sample_property,
        lease_start=date(2025, 12, 1),
        lease_end=date(2026, 2, 15),
    )
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 10),
        lease_end=None,
    )

    result = portfolio_occupancy(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    point = result.points[0]
    assert point["capacity"] == 1
    assert point["occupied"] == 1
    assert point["vacant"] == 0
    assert point["occupancy_rate"] == 100.0


@pytest.mark.django_db
def test_occupancy_handles_inventory_entry_lease_gaps_and_sale(
    landlord_user, sample_property
):
    """Static property/tenant counts would misstate never-rented, gap, and sold months."""
    never_rented = PropertyFactory(owned_by=landlord_user.landlord)
    sold = PropertyFactory(
        owned_by=landlord_user.landlord, sold=date(2026, 3, 15)
    )
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        lease_end=date(2026, 1, 31),
    )
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 3, 1),
        lease_end=None,
    )
    TenantFactory(
        property=sold,
        lease_start=date(2025, 1, 1),
        lease_end=date(2026, 3, 15),
    )

    from rentals.analytics.portfolio import portfolio_occupancy

    result = portfolio_occupancy(
        landlord_user, filters_for("2026-01-01", "2026-04-30")
    )

    assert [
        (point["capacity"], point["occupied"], point["vacant"])
        for point in result.points
    ] == [
        (2, 2, 0),
        (2, 1, 1),
        (2, 2, 0),
        (1, 1, 0),
    ]
    assert all(point["occupancy_rate"] <= 100.0 for point in result.points)


@pytest.mark.django_db
def test_yields_use_raw_latest_valuation_and_annualized_selected_period(
    landlord_user, sample_property
):
    """Value-based net yield would understate the return on invested equity."""
    from rentals.analytics.portfolio import property_yields

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 30),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 31),
        capital_structure_value=None,
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 2, 1),
        capital_structure_value=Decimal("999000.00"),
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("3100.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("620.00"),
        date=date(2026, 1, 12),
        currency="USD",
    )

    result = property_yields(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    row = result.rows[0]
    assert row.property_value == 100000.0
    assert row.valuation_date == date(2025, 12, 30)
    assert row.annualized_revenue == pytest.approx(36500.0)
    assert row.annualized_costs == pytest.approx(7300.0)
    assert row.gross_yield == pytest.approx(29_200 / 100_000 * 100)
    assert row.debt == pytest.approx(40000.0)
    assert row.equity == pytest.approx(60000.0)
    assert row.equity_yield == pytest.approx(29_200 / 60_000 * 100)
    assert row.status == "stale_valuation"


@pytest.mark.django_db
def test_yields_use_net_income_numerator_for_value_and_equity(
    landlord_user, sample_property
):
    from rentals.analytics.portfolio import property_yields

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("12000.00"),
        date=date(2026, 1, 15),
    )
    TransactionFactory(
        property=sample_property,
        category="utilities",
        amount=Decimal("-2000.00"),
        date=date(2026, 1, 20),
    )

    result = property_yields(
        landlord_user,
        filters_for("2026-01-01", "2026-12-31"),
    )
    row = next(row for row in result.rows if row.property_id == sample_property.id)

    assert row.annualized_revenue == pytest.approx(12000)
    assert row.annualized_costs == pytest.approx(2000)
    assert row.gross_yield == pytest.approx(10.0)
    assert row.equity_yield == pytest.approx(16.666666)


@pytest.mark.django_db
def test_yields_exclude_properties_sold_on_or_before_report_end(
    landlord_user, sample_property
):
    """Sold assets excluded from summary value must also be absent from yields."""
    from rentals.analytics.portfolio import property_yields

    sample_property.sold = date(2026, 1, 31)
    sample_property.save(update_fields=["sold"])
    active_property = PropertyFactory(owned_by=landlord_user.landlord)
    for property_ in (sample_property, active_property):
        PropertyCapitalStructureFactory(
            property=property_,
            capital_structure_date=date(2026, 1, 1),
            capital_structure_value=Decimal("100000.00"),
            capital_structure_debt=Decimal("40000.00"),
        )

    result = property_yields(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert [row.property_id for row in result.rows] == [active_property.id]


@pytest.mark.django_db
def test_portfolio_totals_treat_cost_reimbursement_as_contra_expense(
    landlord_user, sample_property
):
    from rentals.analytics.portfolio import portfolio_summary

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 1),
    )
    TransactionFactory(
        property=sample_property,
        category="tax",
        amount=Decimal("-300.00"),
        date=date(2026, 1, 2),
    )
    TransactionFactory(
        property=sample_property,
        category="cost_reimbursement",
        amount=Decimal("-125.00"),
        date=date(2026, 1, 3),
    )

    result = portfolio_summary(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.revenue == pytest.approx(1000)
    assert result.costs == pytest.approx(175)
    assert result.net_income == pytest.approx(825)


@pytest.mark.django_db
def test_missing_valuation_returns_explicit_status_without_fabricated_yield(
    landlord_user, sample_property
):
    """A synthetic zero or guessed denominator would invent property yields."""
    from rentals.analytics.portfolio import property_yields

    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 10),
    )

    row = property_yields(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    ).rows[0]

    assert row.status == "missing_valuation"
    assert row.valuation_date is None
    assert row.property_value is None
    assert row.debt is None
    assert row.equity is None
    assert row.gross_yield is None
    assert row.equity_yield is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("value", "debt", "expected_equity", "expected_status"),
    [
        ("100000.00", "100000.00", 0.0, "zero_equity"),
        ("100000.00", "150000.00", -50000.0, "negative_equity"),
    ],
)
def test_equity_yield_requires_positive_equity(
    landlord_user, sample_property, value, debt, expected_equity, expected_status
):
    """Zero or negative equity cannot be used as a yield denominator."""
    from rentals.analytics.portfolio import property_yields

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal(value),
        capital_structure_debt=Decimal(debt),
    )

    row = property_yields(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    ).rows[0]

    assert row.property_value == 100000.0
    assert row.gross_yield == 0.0
    assert row.equity == expected_equity
    assert row.equity_yield is None
    assert row.status == expected_status


@pytest.mark.django_db
def test_yields_keep_missing_value_and_debt_denominators_null(
    landlord_user, sample_property
):
    """A missing capital input must not be coerced to zero in either yield."""
    from rentals.analytics.portfolio import property_yields

    missing_debt = PropertyFactory(owned_by=landlord_user.landlord)
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=None,
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=missing_debt,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )

    rows = {
        row.property_id: row
        for row in property_yields(
            landlord_user, filters_for("2026-01-01", "2026-01-31")
        ).rows
    }

    assert rows[sample_property.id].debt == 40000.0
    assert rows[sample_property.id].property_value is None
    assert rows[sample_property.id].gross_yield is None
    assert rows[sample_property.id].equity is None
    assert rows[sample_property.id].equity_yield is None
    assert rows[sample_property.id].status == "missing_valuation"
    assert rows[missing_debt.id].property_value == 100000.0
    assert rows[missing_debt.id].debt is None
    assert rows[missing_debt.id].gross_yield == 0.0
    assert rows[missing_debt.id].equity is None
    assert rows[missing_debt.id].equity_yield is None
    assert rows[missing_debt.id].status == "missing_valuation"


@pytest.mark.django_db
def test_yields_mark_either_stale_capital_snapshot_without_dropping_it(
    landlord_user, sample_property
):
    """Staleness must follow value and debt independently while retaining the values."""
    from rentals.analytics.portfolio import property_yields

    stale_debt = PropertyFactory(owned_by=landlord_user.landlord)
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=None,
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=stale_debt,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )
    PropertyCapitalStructureFactory(
        property=stale_debt,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=None,
        capital_structure_debt=Decimal("40000.00"),
    )

    rows = {
        row.property_id: row
        for row in property_yields(
            landlord_user, filters_for("2026-01-01", "2026-01-31")
        ).rows
    }

    for property_id in (sample_property.id, stale_debt.id):
        assert rows[property_id].status == "stale_valuation"
        assert rows[property_id].equity == 60000.0
        assert rows[property_id].equity_yield == 0.0


@pytest.mark.django_db
def test_contribution_preserves_negative_rows_and_portfolio_share_context(
    landlord_user, sample_property
):
    """Dropping losses or their denominator context would misrank contributors."""
    from rentals.analytics.portfolio import property_contribution

    losing_property = PropertyFactory(owned_by=landlord_user.landlord)
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 5),
    )
    TransactionFactory(
        property=losing_property,
        category="utilities",
        amount=Decimal("250.00"),
        date=date(2026, 1, 6),
    )

    result = property_contribution(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )
    rows = {row.property_id: row for row in result.rows}

    assert result.portfolio_net_income == 750.0
    assert rows[sample_property.id].net_income == 1000.0
    assert rows[losing_property.id].net_income == -250.0
    assert rows[sample_property.id].portfolio_share == pytest.approx(133.333333)
    assert rows[losing_property.id].portfolio_share == pytest.approx(-33.333333)


@pytest.mark.django_db
def test_property_breakdown_groups_equity_by_property_across_calendar_periods(
    landlord_user, sample_property
):
    """Currency aggregation or report-date FX would misstate property equity."""
    from rentals.analytics.portfolio import property_breakdown

    sample_property.name = "Anokhina"
    sample_property.sold = date(2026, 3, 15)
    sample_property.save(update_fields=["name", "sold"])
    wandsworth = PropertyFactory(
        owned_by=landlord_user.landlord,
        name="Wandsworth",
        currency="EUR",
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("2.00"),
        date=date(2026, 1, 1),
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("3.00"),
        date=date(2026, 2, 1),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 5),
        capital_structure_value=Decimal("500000.00"),
        capital_structure_debt=Decimal("200000.00"),
    )
    PropertyCapitalStructureFactory(
        property=wandsworth,
        capital_structure_date=date(2026, 1, 10),
        capital_structure_value=Decimal("200000.00"),
        capital_structure_debt=Decimal("50000.00"),
    )
    PropertyCapitalStructureFactory(
        property=wandsworth,
        capital_structure_date=date(2026, 2, 10),
        capital_structure_value=Decimal("250000.00"),
        capital_structure_debt=None,
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-03-31"),
        measure="equity",
    )

    assert result.measure == "equity"
    assert result.measure_label == "Equity"
    assert [series.label for series in result.series] == ["Anokhina", "Wandsworth"]
    assert [series.key for series in result.series] == [
        f"property_{sample_property.id}",
        f"property_{wandsworth.id}",
    ]
    assert [point["period_start"] for point in result.points] == [
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
    anokhina_key = f"property_{sample_property.id}"
    wandsworth_key = f"property_{wandsworth.id}"
    assert result.points[0][anokhina_key] == pytest.approx(300_000)
    assert result.points[0][wandsworth_key] == pytest.approx(300_000)
    assert result.points[1][wandsworth_key] == pytest.approx(650_000)
    assert anokhina_key not in result.points[2]
    assert result.points[2][wandsworth_key] == pytest.approx(650_000)


@pytest.mark.django_db
def test_property_breakdown_keeps_missing_valuation_distinct_from_zero(
    landlord_user, sample_property
):
    """A missing snapshot must not become a genuine zero-valued property."""
    from rentals.analytics.portfolio import property_breakdown

    missing = PropertyFactory(owned_by=landlord_user.landlord, name="Missing")
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("0.00"),
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        measure="property_value",
    )

    assert result.points[0][f"property_{sample_property.id}"] == 0.0
    assert result.points[0][f"property_{missing.id}"] is None
    coverage = {row.property_id: row for row in result.coverage}
    assert coverage[sample_property.id].status == "ok"
    assert coverage[missing.id].status == "missing_valuation"


@pytest.mark.django_db
def test_property_breakdown_preloads_capital_fx_once_for_all_properties_and_periods(
    landlord_user, sample_property, monkeypatch
):
    """Per-property/per-period converter construction would multiply FX queries."""
    import rentals.analytics.portfolio as portfolio

    second = PropertyFactory(owned_by=landlord_user.landlord)
    for property_ in (sample_property, second):
        PropertyCapitalStructureFactory(
            property=property_,
            capital_structure_date=date(2026, 1, 1),
            capital_structure_value=Decimal("100000.00"),
        )
    original = portfolio.preload_converter
    calls = []

    def tracking_preload(rows, reporting_currency):
        calls.append(tuple(rows))
        return original(rows, reporting_currency)

    monkeypatch.setattr(portfolio, "preload_converter", tracking_preload)

    portfolio.property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-03-31"),
        measure="property_value",
    )

    assert len(calls) == 1
    assert len(calls[0]) == 6


@pytest.mark.django_db
def test_property_breakdown_buckets_rental_income_and_hides_sold_property(
    landlord_user, sample_property
):
    """Income must remain in its transaction month and respect sale visibility."""
    from rentals.analytics.portfolio import property_breakdown

    sample_property.sold = date(2026, 3, 1)
    sample_property.save(update_fields=["sold"])
    euro_property = PropertyFactory(
        owned_by=landlord_user.landlord,
        name="Wandsworth",
        currency="EUR",
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("2.00"),
        date=date(2026, 1, 1),
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 15),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("9000.00"),
        date=date(2026, 3, 15),
        currency="USD",
    )
    TransactionFactory(
        property=euro_property,
        category="rent",
        amount=Decimal("500.00"),
        date=date(2026, 2, 15),
        currency="EUR",
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-03-31"),
        measure="rental_income",
    )

    sold_key = f"property_{sample_property.id}"
    euro_key = f"property_{euro_property.id}"
    assert [(point[sold_key], point[euro_key]) for point in result.points[:2]] == [
        (1000.0, 0.0),
        (0.0, 1000.0),
    ]
    assert sold_key not in result.points[2]
    assert result.points[2][euro_key] == 0.0


@pytest.mark.django_db
def test_property_breakdown_retains_property_series_for_every_active_period(
    landlord_user, sample_property
):
    """Collapsing later periods to a portfolio total would erase property identity."""
    from rentals.analytics.portfolio import property_breakdown

    euro_property = PropertyFactory(
        owned_by=landlord_user.landlord, currency="EUR"
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("2.00"),
        date=date(2025, 12, 1),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=euro_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("50000.00"),
        capital_structure_debt=Decimal("10000.00"),
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-02-28"),
        measure="property_value",
    )

    assert result.measure == "property_value"
    assert result.measure_label == "Property value"
    assert result.scale == 1
    assert [series.key for series in result.series] == [
        f"property_{sample_property.id}",
        f"property_{euro_property.id}",
    ]
    assert [
        (point[f"property_{sample_property.id}"], point[f"property_{euro_property.id}"])
        for point in result.points
    ] == [
        (100000.0, 100000.0),
        (100000.0, 100000.0),
    ]


@pytest.mark.django_db
def test_property_breakdown_marks_missing_and_stale_valuation_coverage(
    landlord_user, sample_property
):
    """Unavailable valuation data must not be serialized as genuine zero exposure."""
    from rentals.analytics.portfolio import property_breakdown

    missing = PropertyFactory(owned_by=landlord_user.landlord, currency="EUR")
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        measure="property_value",
    )

    assert missing.currency == "EUR"
    assert result.points[0][f"property_{missing.id}"] is None
    coverage = {row.property_id: row for row in result.coverage}
    assert coverage[missing.id].status == "missing_valuation"
    assert coverage[sample_property.id].status == "stale_valuation"


@pytest.mark.django_db
def test_partial_period_occupancy_clips_leases_and_sales_to_filter_bounds(
    landlord_user, sample_property
):
    """Calendar days outside a partial filter must not affect occupancy."""
    from rentals.analytics.portfolio import portfolio_occupancy, portfolio_summary

    TenantFactory(
        property=sample_property,
        lease_start=date(2025, 1, 1),
        lease_end=date(2026, 1, 5),
    )
    sold = PropertyFactory(
        owned_by=landlord_user.landlord, sold=date(2026, 1, 5)
    )
    TenantFactory(
        property=sold,
        lease_start=date(2025, 1, 1),
        lease_end=None,
    )
    filters = filters_for("2026-01-10", "2026-01-20")

    point = portfolio_occupancy(landlord_user, filters).points[0]
    summary = portfolio_summary(landlord_user, filters)

    assert point["capacity"] == 1
    assert point["occupied"] == 0
    assert summary.rental_inventory_count == 1
    assert summary.occupied == 0
    assert summary.occupancy_rate == 0.0


@pytest.mark.django_db
def test_property_breakdown_excludes_property_sold_on_or_before_period_as_of(
    landlord_user, sample_property
):
    """An end-of-period exposure snapshot must not retain already-sold assets."""
    from rentals.analytics.portfolio import property_breakdown

    sample_property.sold = date(2026, 1, 31)
    sample_property.save(update_fields=["sold"])
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    result = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        measure="property_value",
    )

    assert f"property_{sample_property.id}" not in result.points[0]
    assert result.series == ()
    assert result.coverage == ()


@pytest.mark.django_db
def test_lease_starting_after_sale_never_creates_capacity_or_occupancy(
    landlord_user, sample_property
):
    """Invalid post-sale lease records must not reactivate sold inventory."""
    from rentals.analytics.portfolio import portfolio_occupancy

    sample_property.sold = date(2026, 1, 10)
    sample_property.save(update_fields=["sold"])
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 11),
        lease_end=None,
    )

    point = portfolio_occupancy(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    ).points[0]

    assert point["capacity"] == 0
    assert point["occupied"] == 0
    assert point["vacant"] == 0


@pytest.mark.django_db
def test_summary_reports_value_and_debt_coverage_independently(
    landlord_user, sample_property
):
    """Missing debt cannot be treated as zero or used to fabricate equity."""
    from rentals.analytics.portfolio import portfolio_summary

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )

    summary = portfolio_summary(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert summary.property_value == 100000.0
    assert summary.property_value_status == "ok"
    assert summary.debt is None
    assert summary.debt_status == "missing_valuation"
    assert summary.equity is None
    assert summary.valuation_status == "missing_valuation"


@pytest.mark.django_db
def test_summary_converts_latest_value_and_debt_at_independent_snapshot_dates(
    landlord_user, sample_property
):
    """Converting every capital amount at report end would misstate debt and equity."""
    from rentals.analytics.portfolio import portfolio_summary

    euro_property = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="EUR",
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("2.00"),
        date=date(2026, 1, 1),
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("3.00"),
        date=date(2026, 1, 8),
    )
    FXFactory(
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("4.00"),
        date=date(2026, 1, 20),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 4),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=None,
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 9),
        capital_structure_value=None,
        capital_structure_debt=Decimal("50000.00"),
    )
    PropertyCapitalStructureFactory(
        property=euro_property,
        capital_structure_date=date(2026, 1, 5),
        capital_structure_value=Decimal("400000.00"),
        capital_structure_debt=None,
    )
    PropertyCapitalStructureFactory(
        property=euro_property,
        capital_structure_date=date(2026, 1, 10),
        capital_structure_value=None,
        capital_structure_debt=Decimal("100000.00"),
    )

    result = portfolio_summary(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert result.property_value == pytest.approx(900_000)
    assert result.debt == pytest.approx(350_000)
    assert result.equity == pytest.approx(550_000)


@pytest.mark.django_db
def test_summary_marks_stale_debt_without_presenting_it_as_fresh(
    landlord_user, sample_property
):
    """An old debt snapshot must retain its stale status independently of value."""
    from rentals.analytics.portfolio import portfolio_summary

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_debt=Decimal("40000.00"),
    )

    summary = portfolio_summary(
        landlord_user, filters_for("2026-01-01", "2026-01-31")
    )

    assert summary.property_value_status == "ok"
    assert summary.debt == 40000.0
    assert summary.debt_status == "stale_valuation"
    assert summary.equity == 60000.0


@pytest.mark.django_db
def test_null_native_currency_is_explicit_and_independent_of_reporting_currency(
    landlord_user, auth_client
):
    """Missing native currency must not inherit a request-dependent FX identity."""
    from rentals.analytics.portfolio import property_breakdown

    property_ = PropertyFactory(owned_by=landlord_user.landlord, currency=None)
    PropertyCapitalStructureFactory(
        property=property_,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
    )
    usd_filters = filters_for("2026-01-01", "2026-01-31")
    eur_filters = AnalyticsFilters(
        start=usd_filters.start,
        end=usd_filters.end,
        grain=usd_filters.grain,
        currency="EUR",
        comparison=None,
        property_ids=(),
    )

    usd = property_breakdown(landlord_user, usd_filters, "property_value")
    eur = property_breakdown(landlord_user, eur_filters, "property_value")

    key = f"property_{property_.id}"
    assert [series.key for series in usd.series] == [key]
    assert [series.key for series in eur.series] == [key]
    assert usd.points[0][key] is None
    assert eur.points[0][key] is None
    assert usd.coverage[0].property_id == property_.id
    assert usd.coverage[0].status == "missing_currency"
    response = auth_client.get(
        "/api/v1/analytics/portfolio/property-breakdown/",
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "measure": "property_value",
        },
    )
    assert response.status_code == 200
    assert response.json()["coverage"][0]["property_id"] == property_.id


@pytest.mark.django_db
def test_property_breakdown_coverage_preserves_missing_and_stale_properties(
    landlord_user, sample_property
):
    """A missing peer must not hide that another property's valuation is stale."""
    from rentals.analytics.portfolio import property_breakdown

    missing = PropertyFactory(owned_by=landlord_user.landlord, currency="USD")
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    coverage = property_breakdown(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        "property_value",
    ).coverage

    statuses = {row.property_id: row.status for row in coverage}
    assert statuses[sample_property.id] == "stale_valuation"
    assert statuses[missing.id] == "missing_valuation"


@pytest.mark.django_db
def test_yields_distinguish_zero_and_negative_valuation_statuses(
    landlord_user, sample_property
):
    """Negative valuation data must not be mislabeled as an ordinary zero."""
    from rentals.analytics.portfolio import property_yields

    zero_property = PropertyFactory(owned_by=landlord_user.landlord)
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("-100.00"),
    )
    PropertyCapitalStructureFactory(
        property=zero_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("0.00"),
    )

    rows = {
        row.property_id: row
        for row in property_yields(
            landlord_user, filters_for("2026-01-01", "2026-01-31")
        ).rows
    }

    assert rows[sample_property.id].status == "negative_valuation"
    assert rows[zero_property.id].status == "zero_valuation"
    assert rows[sample_property.id].gross_yield is None
    assert rows[zero_property.id].gross_yield is None


@pytest.mark.django_db
def test_portfolio_services_scope_selected_properties_to_owner(
    landlord_user, other_landlord_user, sample_property
):
    """Trusting requested IDs without owner scoping would leak another portfolio."""
    from rentals.analytics.portfolio import property_contribution

    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("100.00"),
        date=date(2026, 1, 1),
    )
    TransactionFactory(
        property=other_property,
        category="rent",
        amount=Decimal("900.00"),
        date=date(2026, 1, 1),
    )

    result = property_contribution(
        landlord_user,
        filters_for(
            "2026-01-01",
            "2026-01-31",
            property_ids=(sample_property.id, other_property.id),
        ),
    )

    assert [row.property_id for row in result.rows] == [sample_property.id]
    assert result.portfolio_net_income == 100.0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/portfolio/summary/",
        "/api/v1/analytics/portfolio/property-contribution/",
        "/api/v1/analytics/portfolio/yields/",
        "/api/v1/analytics/portfolio/property-breakdown/",
        "/api/v1/analytics/portfolio/occupancy/",
    ],
)
def test_portfolio_endpoints_require_authentication(path):
    """Removing an auth gate would expose portfolio analytics anonymously."""
    assert Client().get(path).status_code == 403


@pytest.mark.django_db
def test_portfolio_endpoints_serialize_explicit_nested_contracts(
    auth_client, sample_property
):
    """Generic dictionary serialization would allow response contract drift."""
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        lease_end=None,
    )
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 10),
    )
    params = {"start": "2026-01-01", "end": "2026-01-31"}

    summary = auth_client.get(
        "/api/v1/analytics/portfolio/summary/", params
    )
    contribution = auth_client.get(
        "/api/v1/analytics/portfolio/property-contribution/", params
    )
    yields = auth_client.get("/api/v1/analytics/portfolio/yields/", params)
    breakdown = auth_client.get(
        "/api/v1/analytics/portfolio/property-breakdown/",
        {**params, "measure": "debt"},
    )
    occupancy = auth_client.get(
        "/api/v1/analytics/portfolio/occupancy/", params
    )

    assert summary.status_code == 200
    assert summary.json()["property_value"] == 100000.0
    assert summary.json()["debt"] == 40000.0
    assert contribution.status_code == 200
    assert contribution.json()["rows"][0]["property_id"] == sample_property.id
    assert yields.status_code == 200
    yield_row = yields.json()["rows"][0]
    assert yield_row["status"] == "ok"
    assert yield_row["debt"] == 40000.0
    assert yield_row["equity"] == 60000.0
    assert yield_row["equity_yield"] == pytest.approx(19.623655913978492)
    assert "net_yield" not in yield_row
    assert breakdown.status_code == 200
    assert breakdown.json()["measure"] == "debt"
    assert breakdown.json()["points"][0][f"property_{sample_property.id}"] == 40000.0
    assert occupancy.status_code == 200
    assert occupancy.json()["points"][0]["occupancy_rate"] == 100.0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "params", "field"),
    [
        (
            "/api/v1/analytics/portfolio/property-breakdown/",
            {"measure": "value_at_risk"},
            "measure",
        ),
        (
            "/api/v1/analytics/portfolio/summary/",
            {"grain": "week"},
            "grain",
        ),
        (
            "/api/v1/analytics/portfolio/summary/",
            {"unexpected": "1"},
            "unexpected",
        ),
        (
            "/api/v1/analytics/portfolio/summary/",
            {"currency": "ZZZ"},
            "currency",
        ),
        (
            "/api/v1/analytics/portfolio/summary/",
            {"comparison": "previous_period"},
            "comparison",
        ),
    ],
)
def test_portfolio_endpoints_strictly_validate_query_values(
    auth_client, path, params, field
):
    """Ignoring invalid analytics state would make copied URLs misleading."""
    response = auth_client.get(path, params)

    assert response.status_code == 400
    assert field in response.json()
