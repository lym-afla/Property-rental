"""API tests for portfolio cash-flow and expense-driver analytics."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from rentals.tests.factories import PropertyFactory, TransactionFactory


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
