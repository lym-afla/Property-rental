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
    """Scaling values or using a future valuation would corrupt yield denominators."""
    from rentals.analytics.portfolio import property_yields

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 31),
        capital_structure_value=Decimal("100000.00"),
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
    assert row.valuation_date == date(2025, 12, 31)
    assert row.annualized_revenue == pytest.approx(36500.0)
    assert row.annualized_costs == pytest.approx(7300.0)
    assert row.gross_yield == pytest.approx(36.5)
    assert row.net_yield == pytest.approx(29.2)
    assert row.status == "stale_valuation"


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
    assert row.gross_yield is None
    assert row.net_yield is None


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
def test_currency_exposure_retains_native_categories_for_every_period(
    landlord_user, sample_property
):
    """Collapsing later periods to a portfolio total would erase currency exposure."""
    from rentals.analytics.portfolio import currency_exposure

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

    result = currency_exposure(
        landlord_user,
        filters_for("2026-01-01", "2026-02-28"),
        measure="property_value",
    )

    assert result.measure == "property_value"
    assert result.measure_label == "Property value"
    assert result.scale == 1
    assert [series.key for series in result.series] == ["EUR", "USD"]
    assert [(point["EUR"], point["USD"]) for point in result.points] == [
        (100000.0, 100000.0),
        (100000.0, 100000.0),
    ]


@pytest.mark.django_db
def test_currency_exposure_marks_missing_and_stale_valuation_coverage(
    landlord_user, sample_property
):
    """Unavailable valuation data must not be serialized as genuine zero exposure."""
    from rentals.analytics.portfolio import currency_exposure

    missing = PropertyFactory(owned_by=landlord_user.landlord, currency="EUR")
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    result = currency_exposure(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        measure="property_value",
    )

    assert missing.currency == "EUR"
    assert result.points[0]["EUR"] is None
    coverage = {row.currency: row for row in result.coverage}
    assert coverage["EUR"].status == "missing_valuation"
    assert coverage["USD"].status == "stale_valuation"


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
def test_valuation_exposure_excludes_property_sold_on_or_before_period_as_of(
    landlord_user, sample_property
):
    """An end-of-period exposure snapshot must not retain already-sold assets."""
    from rentals.analytics.portfolio import currency_exposure

    sample_property.sold = date(2026, 1, 31)
    sample_property.save(update_fields=["sold"])
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    result = currency_exposure(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        measure="property_value",
    )

    assert result.points[0]["USD"] == 0.0
    assert result.coverage[0].status == "no_exposure"


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
    from rentals.analytics.portfolio import currency_exposure

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

    usd = currency_exposure(landlord_user, usd_filters, "property_value")
    eur = currency_exposure(landlord_user, eur_filters, "property_value")

    assert [series.key for series in usd.series] == ["missing_currency"]
    assert [series.key for series in eur.series] == ["missing_currency"]
    assert usd.points[0]["missing_currency"] is None
    assert eur.points[0]["missing_currency"] is None
    assert usd.coverage[0].currency is None
    assert usd.coverage[0].status == "missing_currency"
    response = auth_client.get(
        "/api/v1/analytics/portfolio/currency-exposure/",
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "measure": "property_value",
        },
    )
    assert response.status_code == 200
    assert response.json()["coverage"][0]["currency"] is None


@pytest.mark.django_db
def test_exposure_coverage_preserves_partial_and_stale_conditions_together(
    landlord_user, sample_property
):
    """A missing peer must not hide that the available valuation is stale."""
    from rentals.analytics.portfolio import currency_exposure

    PropertyFactory(owned_by=landlord_user.landlord, currency="USD")
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2025, 12, 1),
        capital_structure_value=Decimal("100000.00"),
    )

    coverage = currency_exposure(
        landlord_user,
        filters_for("2026-01-01", "2026-01-31"),
        "property_value",
    ).coverage[0]

    assert coverage.status == "partial_stale_valuation"
    assert coverage.missing_count == 1
    assert coverage.stale_count == 1


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
        "/api/v1/analytics/portfolio/currency-exposure/",
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
    exposure = auth_client.get(
        "/api/v1/analytics/portfolio/currency-exposure/",
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
    assert yields.json()["rows"][0]["status"] == "ok"
    assert exposure.status_code == 200
    assert exposure.json()["measure"] == "debt"
    assert exposure.json()["points"][0]["USD"] == 40000.0
    assert occupancy.status_code == 200
    assert occupancy.json()["points"][0]["occupancy_rate"] == 100.0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "params", "field"),
    [
        (
            "/api/v1/analytics/portfolio/currency-exposure/",
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
