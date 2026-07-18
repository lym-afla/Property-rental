"""Smoke tests for the new DRF layer (Task 16).

These tests exercise:

* Each ``ModelSerializer`` validates a representative payload drawn from
  the existing factories (Property, Tenant, Transaction, FX).
* The ``ChartDataResponseSerializer`` round-trips a chart payload.
* ``IsOwnerOrReadOnly`` admits the owner and denies a non-owner for both
  model shapes the app uses (``Property.owned_by.user`` and
  ``Tenant.property.owned_by.user``).

The point is wiring + correctness of field names — not exhaustive
validation rules. The existing characterization tests pin the financial
behavior; these only pin the API surface.
"""

from decimal import Decimal

import pytest
from unittest.mock import MagicMock

from rentals.api.permissions import IsOwnerOrReadOnly
from rentals.api.serializers import (
    ChartDataResponseSerializer,
    FXSerializer,
    PropertySerializer,
    TenantSerializer,
    TransactionSerializer,
)
from rentals.tests.factories import (
    FXFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
)


# ---------------------------------------------------------------------------
# Serializer validation smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_serializer_validates_property(landlord_user):
    """PropertySerializer accepts valid factory data and produces a
    valid record (``is_valid()`` True, errors empty)."""
    property_obj = PropertyFactory(owned_by=landlord_user.landlord)
    data = {
        "owned_by": property_obj.owned_by.id,
        "name": "Test Property",
        "location": "Test City",
        "address": "1 Test Street",
        "num_bedrooms": 3,
        "area": "120.50",
        "currency": "USD",
        "sold": None,
    }
    serializer = PropertySerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["name"] == "Test Property"
    assert serializer.validated_data["num_bedrooms"] == 3


@pytest.mark.django_db
def test_serializer_validates_property_serializes_existing_instance(landlord_user):
    """PropertySerializer serializes an existing Property instance."""
    property_obj = PropertyFactory(owned_by=landlord_user.landlord)
    serializer = PropertySerializer(property_obj)
    data = serializer.data
    assert data["id"] == property_obj.id
    assert data["name"] == property_obj.name
    assert data["owned_by"] == property_obj.owned_by.id


@pytest.mark.django_db
def test_serializer_validates_tenant(landlord_user, sample_property):
    """TenantSerializer accepts valid factory data."""
    data = {
        "property": sample_property.id,
        "first_name": "Alice",
        "last_name": "Smith",
        "phone": "555-0100",
        "email": "alice@example.com",
        "lease_start": "2024-01-01",
        "payday": 1,
        "lease_end": None,
    }
    serializer = TenantSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["first_name"] == "Alice"


@pytest.mark.django_db
def test_serializer_validates_transaction(sample_property):
    """TransactionSerializer accepts valid factory data; ``type`` is
    read-only (it is derived from ``category`` in ``Transaction.save``)."""
    data = {
        "date": "2024-01-15",
        "property": sample_property.id,
        "tenant": None,
        "category": "rent",
        "period": "2024-01",
        "currency": "USD",
        "amount": "1500.00",
        "comment": "January rent",
    }
    serializer = TransactionSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    # ``type`` is read-only — it must not appear in validated writable data.
    assert "type" not in serializer.validated_data


@pytest.mark.django_db
def test_serializer_validates_fx():
    """FXSerializer accepts valid long-format FX data."""
    data = {
        "date": "2024-01-01",
        "from_currency": "EUR",
        "to_currency": "USD",
        "rate": "1.10",
    }
    serializer = FXSerializer(data=data)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["from_currency"] == "EUR"


def test_chart_data_response_serializer_round_trip():
    """ChartDataResponseSerializer accepts the chart-data shape that
    ``services.charts.get_chart_data`` returns."""
    payload = {
        "labels": ["2024-01", "2024-02", "2024-03"],
        "datasets": [
            {"label": "Income", "data": [1000, 2000, 1500]},
            {"label": "Expense", "data": [-500, -300, -400]},
        ],
        "currency": "USD",
    }
    serializer = ChartDataResponseSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["currency"] == "USD"
    assert len(serializer.validated_data["labels"]) == 3
    assert len(serializer.validated_data["datasets"]) == 2


def test_chart_data_response_serializer_minimal():
    """ChartDataResponseSerializer tolerates an empty payload (all
    fields are optional — used for error responses)."""
    serializer = ChartDataResponseSerializer(data={})
    assert serializer.is_valid(), serializer.errors


# ---------------------------------------------------------------------------
# IsOwnerOrReadOnly permission tests
# ---------------------------------------------------------------------------


def _build_request(method, user):
    """Build a minimal request-like mock for the permission check."""
    request = MagicMock()
    request.method = method
    request.user = user
    return request


@pytest.mark.django_db
def test_is_owner_or_read_only_allows_owner_get(landlord_user, sample_property):
    """Owner reading their own property: allowed."""
    request = _build_request("GET", landlord_user)
    perm = IsOwnerOrReadOnly()
    assert perm.has_object_permission(request, view=None, obj=sample_property) is True


@pytest.mark.django_db
def test_is_owner_or_read_only_allows_owner_put(landlord_user, sample_property):
    """Owner mutating their own property: allowed."""
    request = _build_request("PUT", landlord_user)
    perm = IsOwnerOrReadOnly()
    assert perm.has_object_permission(request, view=None, obj=sample_property) is True


@pytest.mark.django_db
def test_is_owner_or_read_only_denies_non_owner_get(
    landlord_user, other_landlord_user, sample_property
):
    """Non-owner reading someone else's property: denied.

    The app's data is private to each landlord — even reads must be
    scoped to the owner (this matches the inline 403 checks the template
    views already do in ``handle_element``).
    """
    request = _build_request("GET", other_landlord_user)
    perm = IsOwnerOrReadOnly()
    assert perm.has_object_permission(request, view=None, obj=sample_property) is False


@pytest.mark.django_db
def test_is_owner_or_read_only_denies_non_owner_delete(
    landlord_user, other_landlord_user, sample_property
):
    """Non-owner deleting someone else's property: denied."""
    request = _build_request("DELETE", other_landlord_user)
    perm = IsOwnerOrReadOnly()
    assert perm.has_object_permission(request, view=None, obj=sample_property) is False


@pytest.mark.django_db
def test_is_owner_or_read_only_tenant_via_property(landlord_user, sample_property):
    """Sub-resource shape: ``Tenant.property.owned_by.user``.

    The owner of the tenant's property is allowed; a non-owner is denied.
    Covers the second model shape the permission handles.
    """
    tenant = TenantFactory(property=sample_property)
    perm = IsOwnerOrReadOnly()

    owner_request = _build_request("PUT", landlord_user)
    assert perm.has_object_permission(owner_request, view=None, obj=tenant) is True

    from rentals.tests.factories import UserFactory
    other = UserFactory(is_landlord=True)
    non_owner_request = _build_request("DELETE", other)
    assert perm.has_object_permission(non_owner_request, view=None, obj=tenant) is False
