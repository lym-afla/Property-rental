"""Tests for the ``with_stats`` aggregate endpoints (Task 6).

These cover the two ``@action`` endpoints that return entities pre-joined
with the P&L / rent / debt aggregates the SPA tables need:

* ``GET /api/v1/properties/with_stats/?as_of=...&currency=...`` —
  properties + per-property income / expense / net (all-time + YTD).
* ``GET /api/v1/tenants/with_stats/?as_of=...&currency=...`` —
  tenants + rent_rate / revenue (all-time + YTD) / debt.

The assertions are deliberately **loose** (field presence, not exact
values): the underlying aggregates depend on FX rate rows, and
pinning exact numbers would make the tests fragile against future FX
seed changes. The characterization tests already pin the math.
"""

from datetime import date
from decimal import Decimal

import pytest

from rentals.tests.factories import (
    LeaseRentFactory,
    TenantFactory,
    TransactionFactory,
)


# ---------------------------------------------------------------------------
# Properties with_stats
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_properties_with_stats_requires_auth(db, client):
    """Unauthenticated GET on /api/v1/properties/with_stats/ -> 401/403."""
    resp = client.get("/api/v1/properties/with_stats/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_properties_with_stats_returns_aggregates(auth_client, sample_property):
    """GET /api/v1/properties/with_stats/ -> 200 with P&L aggregate fields.

    Asserts field PRESENCE, not exact values (FX rates make exact-value
    asserts brittle; the math is pinned by ``test_financials_char``).
    """
    # Create a transaction so there's data to aggregate.
    TransactionFactory(
        property=sample_property,
        amount=Decimal("1000.00"),
        currency="USD",
        category="rent",
        date=date(2024, 1, 15),
        period="2024-01",
    )
    resp = auth_client.get(
        "/api/v1/properties/with_stats/?as_of=2024-06-15&currency=USD"
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert len(data) >= 1
    first = data[0]
    # Aggregate fields present.
    assert "gross_income_all_time" in first
    assert "expenses_all_time" in first
    assert "net_income_all_time" in first
    assert "gross_income_ytd" in first
    assert "expenses_ytd" in first
    assert "net_income_ytd" in first


# ---------------------------------------------------------------------------
# Tenants with_stats
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tenants_with_stats_returns_aggregates(auth_client, sample_property):
    """GET /api/v1/tenants/with_stats/ -> 200 with rent/revenue/debt fields."""
    tenant = TenantFactory(property=sample_property)
    LeaseRentFactory(tenant=tenant, rent=Decimal("1200.00"))
    TransactionFactory(
        property=sample_property,
        tenant=tenant,
        amount=Decimal("1200.00"),
        currency="USD",
        category="rent",
        date=date(2024, 1, 15),
        period="2024-01",
    )
    resp = auth_client.get(
        "/api/v1/tenants/with_stats/?as_of=2024-06-15&currency=USD"
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert len(data) >= 1
    first = data[0]
    assert "rent_rate" in first
    assert "revenue_all_time" in first
    assert "revenue_ytd" in first
    assert "debt" in first
