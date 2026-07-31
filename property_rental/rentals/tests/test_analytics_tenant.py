"""Behavior and API tests for tenant rent-performance analytics."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.tests.factories import (
    FXFactory,
    LeaseRentFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)


def filters_for(start, end, grain=Grain.MONTH, currency="USD"):
    return AnalyticsFilters(
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
        grain=grain,
        currency=currency,
        comparison=None,
        property_ids=(),
    )


@pytest.mark.django_db
def test_rent_performance_uses_property_native_currency_and_canonical_balances(
    landlord_user,
):
    """A reporting-currency branch or client-side rebucketing would change the contractual balances."""
    from rentals.analytics.tenant import tenant_rent_performance

    property_ = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="GBP",
    )
    tenant = TenantFactory(
        property=property_,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="GBP",
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 2, 5),
        rent=Decimal("1200.00"),
        currency="GBP",
    )
    for payment_date, amount in (
        (date(2026, 1, 20), "1000.00"),
        (date(2026, 2, 10), "1000.00"),
        (date(2026, 3, 2), "1400.00"),
    ):
        TransactionFactory(
            property=property_,
            tenant=tenant,
            category="rent",
            amount=Decimal(amount),
            currency="GBP",
            date=payment_date,
        )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-03-31", currency="USD"),
    )

    assert [point["expected"] for point in result.points] == [1_000, 1_200, 1_200]
    assert [point["received"] for point in result.points] == [1_000, 1_000, 1_400]
    assert [point["variance"] for point in result.points] == [0, -200, 200]
    assert [point["cumulative_arrears"] for point in result.points] == [0, -200, 0]
    assert result.currency == tenant.property.currency


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("lease_start", "payday", "expected"),
    [
        (date(2026, 1, 3), 5, 1000.0),
        (date(2026, 1, 6), 5, 0.0),
        (date(2026, 1, 31), 31, 1000.0),
    ],
)
def test_rent_performance_generates_one_due_only_for_eligible_months(
    landlord_user, sample_property, lease_start, payday, expected
):
    """Charging before lease commencement or dropping February's clamped payday would misstate expected rent."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=lease_start,
        payday=payday,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=lease_start,
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-02-01", "2026-02-28")
        if payday == 31
        else filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.points[0]["expected"] == expected


@pytest.mark.django_db
def test_rent_performance_selects_rate_effective_on_each_due_date(
    landlord_user, sample_property
):
    """Applying a rate change before its first contractual due would rewrite prior expected rent."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    for effective_date, amount in (
        (date(2026, 1, 1), "1000.00"),
        (date(2026, 1, 5), "1200.00"),
        (date(2026, 1, 6), "1400.00"),
    ):
        LeaseRentFactory(
            tenant=tenant,
            date_rent_set=effective_date,
            rent=Decimal(amount),
            currency="USD",
        )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-02-28"),
    )

    assert [point["expected"] for point in result.points] == [1200.0, 1400.0]


@pytest.mark.django_db
def test_rent_performance_attributes_only_unambiguous_legacy_rent(
    landlord_user, sample_property
):
    """Property-wide legacy sums would double-count unassigned rent during overlapping leases."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        lease_end=date(2026, 3, 31),
        payday=5,
    )
    TenantFactory(
        property=sample_property,
        lease_start=date(2026, 2, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    for payment_date, amount, linked_tenant in (
        (date(2026, 1, 20), "1000.00", None),
        (date(2026, 2, 10), "9000.00", None),
        (date(2026, 2, 20), "600.00", tenant),
        (date(2026, 4, 1), "7000.00", None),
    ):
        TransactionFactory(
            property=sample_property,
            tenant=linked_tenant,
            category="rent",
            amount=Decimal(amount),
            currency="USD",
            date=payment_date,
        )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-04-30"),
    )

    assert [point["received"] for point in result.points] == [1000.0, 600.0, 0.0, 0.0]


@pytest.mark.django_db
def test_rent_performance_converts_rates_and_receipts_to_property_currency(
    landlord_user,
):
    """Converting to the caller's default currency would violate the entity-native contract."""
    from rentals.analytics.tenant import tenant_rent_performance

    property_ = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="GBP",
    )
    tenant = TenantFactory(
        property=property_,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    FXFactory(
        date=date(2026, 1, 5),
        from_currency="USD",
        to_currency="GBP",
        rate=Decimal("0.80"),
    )
    FXFactory(
        date=date(2026, 1, 10),
        from_currency="EUR",
        to_currency="GBP",
        rate=Decimal("0.90"),
    )
    TransactionFactory(
        property=property_,
        tenant=tenant,
        category="rent",
        amount=Decimal("1000.00"),
        currency="EUR",
        date=date(2026, 1, 10),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31", currency="USD"),
    )

    assert result.currency == "GBP"
    assert result.points[0]["expected"] == 800.0
    assert result.points[0]["received"] == 900.0
    assert result.points[0]["variance"] == 100.0


@pytest.mark.django_db
def test_rent_performance_tracks_rate_changes_partial_and_missing_payments(
    landlord_user, sample_property
):
    """Static rates or omitted empty months would hide the tenant's arrears."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        lease_end=date(2026, 4, 15),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 3, 1),
        rent=Decimal("1200.00"),
        currency="USD",
    )
    for payment_date, amount in (
        (date(2026, 1, 5), "1000.00"),
        (date(2026, 2, 5), "600.00"),
        (date(2026, 4, 10), "1200.00"),
        (date(2026, 5, 10), "300.00"),
    ):
        TransactionFactory(
            property=sample_property,
            tenant=tenant,
            category="rent",
            amount=Decimal(amount),
            currency="USD",
            date=payment_date,
        )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-05-31"),
    )

    assert result.scale == 1
    assert result.currency == "USD"
    assert [point["expected"] for point in result.points] == [
        1000.0,
        1000.0,
        1200.0,
        1200.0,
        0.0,
    ]
    assert [point["received"] for point in result.points] == [
        1000.0,
        600.0,
        0.0,
        1200.0,
        300.0,
    ]
    assert [point["variance"] for point in result.points] == [
        0.0,
        -400.0,
        -1200.0,
        0.0,
        300.0,
    ]
    assert [point["cumulative_arrears"] for point in result.points] == [
        0.0,
        -400.0,
        -1600.0,
        -1600.0,
        -1300.0,
    ]


@pytest.mark.django_db
def test_rent_performance_uses_contract_due_date_without_collection_grace(
    landlord_user, sample_property
):
    """Applying scheduler collection grace would understate contractual expected rent."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2025, 12, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2025, 12, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-06"),
    )

    assert result.points[0]["expected"] == 1000.0
    assert result.points[0]["variance"] == -1000.0


@pytest.mark.django_db
def test_rent_performance_converts_tenant_scoped_received_payments(
    landlord_user, sample_property
):
    """Face-value or property-wide sums would misstate cross-currency receipts."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    peer = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    FXFactory(
        date=date(2026, 1, 5),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.25"),
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("800.00"),
        currency="EUR",
        date=date(2026, 1, 5),
    )
    TransactionFactory(
        property=sample_property,
        tenant=peer,
        category="rent",
        amount=Decimal("9000.00"),
        currency="USD",
        date=date(2026, 1, 5),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.points[0]["expected"] == 1000.0
    assert result.points[0]["received"] == 1000.0
    assert result.points[0]["variance"] == 0.0


@pytest.mark.django_db
def test_rent_performance_marks_missing_fx_without_using_face_value(
    landlord_user, sample_property
):
    """A missing conversion path must not silently treat foreign rent as USD."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("800.00"),
        currency="EUR",
        date=date(2026, 1, 5),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.status == "missing_fx"
    assert result.points[0]["expected"] == 1000.0
    assert result.points[0]["received"] is None
    assert result.points[0]["variance"] is None
    assert result.points[0]["status"] == "missing_fx"


@pytest.mark.django_db
def test_rent_performance_keeps_signed_overpayment(
    landlord_user, sample_property
):
    """Clamping the running balance would hide advance rent payments."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1500.00"),
        currency="USD",
        date=date(2026, 1, 5),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.points[0]["variance"] == 500.0
    assert result.points[0]["cumulative_arrears"] == 500.0


@pytest.mark.django_db
def test_rent_performance_carries_pre_range_unpaid_rent_into_first_point(
    landlord_user, sample_property
):
    """Resetting the running balance at the range start would hide old arrears."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 11, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 11, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1000.00"),
        currency="USD",
        date=date(2026, 12, 5),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-12-01", "2026-12-31"),
    )

    assert result.opening_arrears == -1000.0
    assert result.points[0]["variance"] == 0.0
    assert result.points[0]["cumulative_arrears"] == -1000.0


@pytest.mark.django_db
def test_rent_performance_carries_pre_range_overpayment_into_first_point(
    landlord_user, sample_property
):
    """Clamping the opening balance would discard a tenant's advance payment."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 11, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 11, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1500.00"),
        currency="USD",
        date=date(2026, 11, 5),
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1000.00"),
        currency="USD",
        date=date(2026, 12, 5),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-12-01", "2026-12-31"),
    )

    assert result.opening_arrears == 500.0
    assert result.points[0]["variance"] == 0.0
    assert result.points[0]["cumulative_arrears"] == 500.0


@pytest.mark.django_db
def test_rent_performance_marks_missing_rate_without_fabricating_expected(
    landlord_user, sample_property
):
    """A due month without rate history must not be treated as zero rent."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.status == "missing_rent_rate"
    assert result.points[0]["expected"] is None
    assert result.points[0]["variance"] is None
    assert result.points[0]["cumulative_arrears"] is None
    assert result.points[0]["status"] == "missing_rent_rate"


@pytest.mark.django_db
def test_rent_performance_api_rejects_cross_owner_and_serializes_boundaries(
    auth_client, sample_property, other_landlord_user
):
    """The API must expose ISO buckets without allowing tenant enumeration."""
    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_tenant = TenantFactory(property=other_property)

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "grain": "month",
        },
    )
    forbidden = auth_client.get(
        f"/api/v1/analytics/tenants/{other_tenant.id}/rent-performance/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert response.status_code == 200
    assert response.json()["opening_arrears"] == 0.0
    assert response.json()["points"][0] == {
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "expected": 1000.0,
        "received": 0.0,
        "variance": -1000.0,
        "cumulative_arrears": -1000.0,
        "status": "ok",
        "issues": [],
    }
    assert forbidden.status_code == 404


@pytest.mark.django_db
def test_rent_performance_preserves_independent_missing_data_issues(
    landlord_user, sample_property
):
    """Collapsing errors would hide opening-rate and receipt-FX failures."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 2, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("800.00"),
        currency="EUR",
        date=date(2026, 3, 10),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-03-01", "2026-03-31"),
    )

    assert result.opening_arrears is None
    assert result.opening_issues == (
        "missing_rent_rate",
        "incomplete_opening_history",
    )
    assert result.points[0]["issues"] == (
        "missing_received_fx",
        "incomplete_opening_history",
    )
    assert result.issues == (
        "missing_rent_rate",
        "missing_received_fx",
        "incomplete_opening_history",
    )


@pytest.mark.django_db
def test_rent_performance_api_serializes_all_independent_issues(
    auth_client, sample_property
):
    """Strict serialization must retain every independent missing-data cause."""
    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 2, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("800.00"),
        currency="EUR",
        date=date(2026, 3, 10),
    )

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {"start": "2026-03-01", "end": "2026-03-31"},
    )

    assert response.status_code == 200
    assert response.json()["opening_issues"] == [
        "missing_rent_rate",
        "incomplete_opening_history",
    ]
    assert response.json()["points"][0]["issues"] == [
        "missing_received_fx",
        "incomplete_opening_history",
    ]
    assert response.json()["issues"] == [
        "missing_rent_rate",
        "missing_received_fx",
        "incomplete_opening_history",
    ]


@pytest.mark.django_db
def test_rent_due_before_partial_range_start_is_part_of_opening_balance(
    landlord_user, sample_property
):
    """A mid-month range must not repeat rent already due earlier that month."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-10", "2026-01-31"),
    )

    assert result.opening_arrears == -1000.0
    assert result.points[0]["expected"] == 0.0
    assert result.points[0]["cumulative_arrears"] == -1000.0


@pytest.mark.django_db
def test_payday_after_partial_range_start_remains_in_selected_expected_rent(
    landlord_user, sample_property
):
    """A due date after a mid-month start belongs to the selected period."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=15,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-10", "2026-01-31"),
    )

    assert result.opening_arrears == 0.0
    assert result.points[0]["expected"] == 1000.0
    assert result.points[0]["variance"] == -1000.0


@pytest.mark.django_db
def test_rent_due_after_lease_end_is_not_expected(
    landlord_user, sample_property
):
    """A payday after vacation must not create rent due for that month."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2025, 12, 1),
        lease_end=date(2026, 1, 4),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2025, 12, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.points[0]["expected"] == 0.0


@pytest.mark.django_db
def test_rent_performance_uses_due_and_payment_dates_for_fx(
    landlord_user, sample_property
):
    """Using one bucket-end FX rate would misstate scheduled and received rent."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="EUR",
    )
    FXFactory(
        date=date(2026, 1, 5),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("2.00"),
    )
    FXFactory(
        date=date(2026, 1, 10),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("3.00"),
    )
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        category="rent",
        amount=Decimal("1000.00"),
        currency="EUR",
        date=date(2026, 1, 10),
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-01-01", "2026-01-31"),
    )

    assert result.points[0]["expected"] == 2000.0
    assert result.points[0]["received"] == 3000.0
    assert result.points[0]["variance"] == 1000.0


@pytest.mark.django_db
def test_incomplete_opening_balance_propagates_to_cumulative_issues(
    landlord_user, sample_property
):
    """Known selected-period values cannot repair an unknown opening balance."""
    from rentals.analytics.tenant import tenant_rent_performance

    tenant = TenantFactory(
        property=sample_property,
        lease_start=date(2026, 1, 1),
        payday=5,
    )
    LeaseRentFactory(
        tenant=tenant,
        date_rent_set=date(2026, 2, 1),
        rent=Decimal("1000.00"),
        currency="USD",
    )

    result = tenant_rent_performance(
        landlord_user,
        tenant.id,
        filters_for("2026-03-01", "2026-03-31"),
    )

    assert result.points[0]["expected"] == 1000.0
    assert result.points[0]["received"] == 0.0
    assert result.points[0]["variance"] == -1000.0
    assert result.points[0]["cumulative_arrears"] is None
    assert "incomplete_opening_history" in result.points[0]["issues"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "field"),
    [
        ({"start": "2026-01-01", "end": "2026-01-31", "bogus": "1"}, "bogus"),
        ({"start": "2026-01-01", "end": "2026-01-31", "currency": "AUD"}, "currency"),
    ],
)
def test_rent_performance_api_rejects_unknown_and_unsupported_queries(
    auth_client, sample_property, query, field
):
    """Entity analytics must reject filters it cannot honor."""
    tenant = TenantFactory(property=sample_property)

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/", query
    )

    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/properties/1/valuation/",
        "/api/v1/analytics/tenants/1/rent-performance/",
    ],
)
def test_entity_analytics_requires_authentication(path):
    """Removing authentication would expose entity financial histories."""
    assert Client().get(path).status_code == 403
