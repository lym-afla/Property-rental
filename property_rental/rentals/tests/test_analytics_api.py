"""API tests for portfolio cash-flow and expense-driver analytics."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from rentals.api.analytics_serializers import YieldRowSerializer
from rentals.tests.factories import (
    LeaseRentFactory,
    PropertyCapitalStructureFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)


def valid_yield_row():
    return {
        "property_id": 1,
        "property_name": "Alpha",
        "valuation_date": "2026-01-01",
        "property_value": 100000.0,
        "debt": 40000.0,
        "equity": 60000.0,
        "annualized_revenue": 10000.0,
        "annualized_costs": 2000.0,
        "gross_yield": 10.0,
        "equity_yield": 13.333333,
        "status": "ok",
    }


@pytest.mark.django_db
def test_tenant_rent_performance_api_owns_native_currency_and_rejects_override(
    auth_client, landlord_user
):
    """Accepting a reporting-currency override would make one tenant chart cache multiple currencies."""
    property_ = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="EUR",
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
        currency="EUR",
    )

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )
    override = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "currency": "USD",
        },
    )

    assert response.status_code == 200
    assert response.json()["currency"] == "EUR"
    assert response.json()["points"][0]["expected"] == 1000.0
    assert override.status_code == 400
    assert "currency" in override.json()


@pytest.mark.django_db
def test_tenant_rent_performance_api_rejects_missing_property_currency(
    auth_client, landlord_user
):
    """Falling back to a user currency would conceal an unavailable native denomination."""
    property_ = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency=None,
    )
    tenant = TenantFactory(
        property=property_,
        lease_start=date(2026, 1, 1),
        payday=5,
    )

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "missing_currency"


@pytest.mark.django_db
@pytest.mark.parametrize("default_currency", [None, ""])
def test_tenant_rent_performance_api_does_not_require_user_reporting_currency(
    auth_client, landlord_user, default_currency
):
    """Routing tenant filters through portfolio currency validation would reject valid native data."""
    landlord_user.default_currency = default_currency
    landlord_user.save(update_fields=["default_currency"])
    property_ = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="EUR",
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
        currency="EUR",
    )

    response = auth_client.get(
        f"/api/v1/analytics/tenants/{tenant.id}/rent-performance/",
        {"start": "2026-01-01", "end": "2026-01-31", "grain": "month"},
    )

    assert response.status_code == 200
    assert response.json()["currency"] == "EUR"
    assert response.json()["points"][0]["expected"] == 1000.0


@pytest.mark.parametrize("field", ["debt", "equity", "equity_yield"])
def test_yield_serializer_rejects_omitted_denominator_contract_fields(field):
    """Optional serializer fields would erase missing-versus-omitted semantics."""
    payload = valid_yield_row()
    del payload[field]

    serializer = YieldRowSerializer(data=payload)

    assert serializer.is_valid() is False
    assert field in serializer.errors


def test_yield_serializer_rejects_non_finite_and_legacy_yield_fields():
    """NaN and the legacy net-yield alias are not valid wire values."""
    non_finite = valid_yield_row()
    non_finite["debt"] = float("nan")
    legacy = valid_yield_row()
    del legacy["equity_yield"]
    legacy["net_yield"] = 8.0

    nan_serializer = YieldRowSerializer(data=non_finite)
    legacy_serializer = YieldRowSerializer(data=legacy)

    assert nan_serializer.is_valid() is False
    assert "debt" in nan_serializer.errors
    assert legacy_serializer.is_valid() is False
    assert "net_yield" in legacy_serializer.errors


@pytest.mark.parametrize(
    ("equity", "status"),
    [(0.0, "zero_equity"), (-50000.0, "negative_equity")],
)
def test_yield_serializer_accepts_explicit_equity_denominator_statuses(
    equity, status
):
    """The wire status must explain why a non-positive equity yield is null."""
    payload = valid_yield_row()
    payload.update(equity=equity, equity_yield=None, status=status)

    serializer = YieldRowSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_cash_flow_requires_authentication(sample_property):
    """Removing the auth gate would expose portfolio financial data anonymously."""
    response = Client().get("/api/v1/analytics/portfolio/cash-flow/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_cash_flow_scopes_transactions_to_requesting_landlord(
    auth_client, sample_property, other_landlord_user
):
    """Dropping user scoping would leak another landlord's income into this trend."""
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    TransactionFactory(
        property=sample_property,
        category="rent",
        amount=Decimal("2000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )
    TransactionFactory(
        property=other_property,
        category="rent",
        amount=Decimal("9000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )

    response = auth_client.get(
        "/api/v1/analytics/portfolio/cash-flow/",
        {"start": "2026-01-01", "end": "2026-01-31", "grain": "month"},
    )

    assert response.status_code == 200
    assert response.json()["points"][0]["rent"] == 2000.0


@pytest.mark.django_db
def test_cash_flow_rejects_non_iso_date(auth_client):
    """Relaxing date parsing would make URL filter boundaries ambiguous."""
    response = auth_client.get(
        "/api/v1/analytics/portfolio/cash-flow/",
        {"start": "2026-1-01", "end": "2026-01-31"},
    )

    assert response.status_code == 400
    assert "start" in response.json()


@pytest.mark.django_db
def test_cash_flow_emits_explicit_series_kinds(auth_client, sample_property):
    """Omitting kinds would force the frontend to reimplement category classification."""
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

    response = auth_client.get(
        "/api/v1/analytics/portfolio/cash-flow/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert response.status_code == 200
    kinds = {item["key"]: item["kind"] for item in response.json()["series"]}
    assert kinds["rent"] == "income_category"
    assert kinds["utilities"] == "expense_category"
    assert kinds["total_income"] == "income_total"
    assert kinds["total_expenses"] == "expense_total"
    assert kinds["net_income"] == "net"


@pytest.mark.django_db
def test_expense_drivers_emits_only_expense_series(auth_client, sample_property):
    """Including income in expense drivers would hide the real cost drivers."""
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

    response = auth_client.get(
        "/api/v1/analytics/portfolio/expenses/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert response.status_code == 200
    assert response.json()["series"] == [
        {"key": "utilities", "label": "Utilities", "kind": "expense_category"}
    ]


@pytest.mark.django_db
def test_property_breakdown_api_exposes_equity_by_property(auth_client, sample_property):
    """Keeping the currency route or omitting equity would break the dashboard contract."""
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )

    response = auth_client.get(
        "/api/v1/analytics/portfolio/property-breakdown/",
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "grain": "month",
            "measure": "equity",
        },
    )

    assert response.status_code == 200
    assert response.json()["metric"] == "property_breakdown"
    assert response.json()["measure"] == "equity"
    assert response.json()["series"] == [
        {
            "key": f"property_{sample_property.id}",
            "label": sample_property.name,
            "kind": "property",
        }
    ]
    assert response.json()["points"][0][f"property_{sample_property.id}"] == 60000.0
    assert response.json()["coverage"][0]["property_id"] == sample_property.id


@pytest.mark.django_db
def test_property_breakdown_api_removes_currency_exposure_route(auth_client):
    """The retired route must not preserve two competing analytics contracts."""
    response = auth_client.get(
        "/api/v1/analytics/portfolio/currency-exposure/",
        {"start": "2026-01-01", "end": "2026-01-31"},
    )

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "extra_params"),
    [
        ("/api/v1/analytics/portfolio/cash-flow/", {}),
        ("/api/v1/analytics/portfolio/expenses/", {}),
        ("/api/v1/analytics/portfolio/summary/", {}),
        ("/api/v1/analytics/portfolio/property-contribution/", {}),
        ("/api/v1/analytics/portfolio/yields/", {}),
        (
            "/api/v1/analytics/portfolio/property-breakdown/",
            {"measure": "rental_income"},
        ),
    ],
)
def test_portfolio_endpoints_return_typed_non_500_when_fx_is_missing(
    auth_client, landlord_user, path, extra_params
):
    """An absent conversion rate must be actionable API data, never a server error."""
    property_eur = PropertyFactory(
        owned_by=landlord_user.landlord,
        currency="EUR",
    )
    PropertyCapitalStructureFactory(
        property=property_eur,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    TransactionFactory(
        property=property_eur,
        category="rent",
        amount=Decimal("1000.00"),
        date=date(2026, 1, 10),
        currency="EUR",
    )
    TransactionFactory(
        property=property_eur,
        category="utilities",
        amount=Decimal("-100.00"),
        date=date(2026, 1, 12),
        currency="EUR",
    )

    response = auth_client.get(
        path,
        {
            "start": "2026-01-01",
            "end": "2026-01-31",
            "currency": "USD",
            **extra_params,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "missing_fx"


@pytest.mark.django_db
def test_profit_loss_requires_authentication():
    """Removing the auth gate would expose a complete financial statement."""
    response = Client().get("/api/v1/analytics/portfolio/profit-loss/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_profit_loss_endpoint_returns_typed_statement_and_excludes_foreign_property(
    auth_client, landlord_user, other_landlord_user
):
    """Requested property IDs must remain subordinate to authenticated ownership."""
    own_property = PropertyFactory(owned_by=landlord_user.landlord)
    foreign_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    TransactionFactory(
        property=own_property,
        category="rent",
        amount=Decimal("2000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )
    TransactionFactory(
        property=foreign_property,
        category="rent",
        amount=Decimal("9000.00"),
        date=date(2026, 1, 10),
        currency="USD",
    )

    response = auth_client.get(
        "/api/v1/analytics/portfolio/profit-loss/",
        {
            "end": "2026-07-30",
            "currency": "USD",
            "property": [own_property.id, foreign_property.id],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metric"] == "profit_and_loss"
    assert payload["currency"] == "USD"
    assert payload["columns"][-1] == {
        "key": "2026",
        "label": "2026YTD",
        "start": "2026-01-01",
        "end": "2026-07-30",
    }
    rent = next(row for row in payload["rows"] if row["key"] == "rent")
    assert rent == {
        "key": "rent",
        "label": "Rent",
        "kind": "income",
        "values": {"2026": 2000.0},
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"end": "2026-7-30"}, "end"),
        ({"currency": "CAD"}, "currency"),
        ({"property": "not-an-id"}, "property"),
        ({"property": "0"}, "property"),
    ],
)
def test_profit_loss_rejects_invalid_filters(auth_client, params, field):
    """Permissive query parsing would make statement scope or units ambiguous."""
    response = auth_client.get(
        "/api/v1/analytics/portfolio/profit-loss/", params
    )

    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.django_db
def test_profit_loss_rejects_filters_outside_its_contract(auth_client):
    """Accepting chart filters would imply unsupported P&L period semantics."""
    response = auth_client.get(
        "/api/v1/analytics/portfolio/profit-loss/", {"grain": "month"}
    )

    assert response.status_code == 400
    assert response.json() == {"grain": "Unknown filter."}
