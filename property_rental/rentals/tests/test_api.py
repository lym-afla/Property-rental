"""Smoke tests for the new DRF layer (Task 16) + endpoint wiring (Task 17).

These tests exercise:

* Each ``ModelSerializer`` validates a representative payload drawn from
  the existing factories (Property, Tenant, Transaction, FX).
* The ``ChartDataResponseSerializer`` round-trips a chart payload.
* ``IsOwnerOrReadOnly`` admits the owner and denies a non-owner for both
  model shapes the app uses (``Property.owned_by.user`` and
  ``Tenant.property.owned_by.user``).
* (Task 17) The ``/api/v1/`` endpoints enforce per-user querysets and
  ownership forcing on create. These IDOR tests prove that User A cannot
  list/retrieve/create-against User B's records.

The point is wiring + correctness of field names — not exhaustive
validation rules. The existing characterization tests pin the financial
behavior; these only pin the API surface.
"""

from decimal import Decimal

import pytest
from unittest.mock import MagicMock

from django.test import Client

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
    UserFactory,
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


# ---------------------------------------------------------------------------
# Task 17: /api/v1/ endpoint wiring + per-user scoping (IDOR proof)
# ---------------------------------------------------------------------------
#
# The four ``ModelViewSet``s registered under ``/api/v1/`` MUST scope every
# queryset by the requesting user's ownership (so a LIST/RETRIEVE for User A
# can never surface User B's rows) and MUST force ownership on create (so a
# client cannot POST a record pointing at another landlord's ``owned_by`` /
# ``property`` / ``tenant`` FK — the IDOR class of bug the serializers leave
# writable). These tests pin both properties; if any of them regress, the
# API layer has an IDOR hole.


def test_property_list_requires_auth(db, client):
    """Unauthenticated GET on /api/v1/properties/ → 401/403.

    ``REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`` is ``IsAuthenticated``,
    so a missing session cookie must be rejected before any data leaks.
    """
    resp = client.get("/api/v1/properties/")
    assert resp.status_code in (401, 403)


def _results(resp):
    """Pull the list of records out of a DRF list response.

    Handles both the paginated shape (``{"results": [...]}``) and the
    no-pagination shape (``[...]``) since the app's REST_FRAMEWORK config
    does not enable a default pagination class.
    """
    payload = resp.json()
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"]
    return payload


@pytest.mark.django_db
def test_property_list_returns_only_own_properties(auth_client, sample_property):
    """Authenticated LIST returns 200 and the caller's own property IDs."""
    resp = auth_client.get("/api/v1/properties/")
    assert resp.status_code == 200
    ids = [p["id"] for p in _results(resp)]
    assert sample_property.id in ids


@pytest.mark.django_db
def test_property_list_excludes_other_landlords(
    auth_client, sample_property, other_landlord_user
):
    """User A's LIST must NOT include User B's property (per-user queryset)."""
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    resp = auth_client.get("/api/v1/properties/")
    assert resp.status_code == 200
    ids = [p["id"] for p in _results(resp)]
    assert sample_property.id in ids
    assert other_property.id not in ids


@pytest.mark.django_db
def test_property_retrieve_other_landlord_returns_404(
    auth_client, other_landlord_user
):
    """RETRIEVE /api/v1/properties/<other_pk>/ → 404 (not 403, not 200).

    Per-user queryset filtering means an out-of-scope PK simply does not
    exist from this caller's perspective (defeating enumeration).
    """
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    resp = auth_client.get(f"/api/v1/properties/{other_property.id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_create_property_assigns_to_requesting_user(auth_client, landlord_user):
    """POST ignores client-supplied ``owned_by`` and forces it to requester.

    The serializer leaves ``owned_by`` writable so the view layer can set
    it; if the ViewSet didn't override ``perform_create``, a client could
    set ``owned_by`` to another landlord's PK — an IDOR. The override MUST
    pin the FK to ``request.user.landlord`` regardless of payload.
    """
    other_user = UserFactory(is_landlord=True)
    payload = {
        "owned_by": other_user.landlord.id,  # Attempted IDOR
        "name": "Hijacked Property",
        "location": "Nowhere",
        "num_bedrooms": 2,
        "currency": "USD",
    }
    resp = auth_client.post("/api/v1/properties/", payload, content_type="application/json")
    assert resp.status_code == 201, resp.content
    created_id = resp.json()["id"]
    # Reassign test: the record MUST be owned by the requesting user, not
    # the client-supplied other landlord. Read it back via the same user's
    # scoped queryset to confirm ownership.
    from rentals.models import Property
    created = Property.objects.get(id=created_id)
    assert created.owned_by_id == landlord_user.landlord.id
    assert created.owned_by_id != other_user.landlord.id


@pytest.mark.django_db
def test_tenant_list_excludes_other_landlords(auth_client, sample_property, other_landlord_user):
    """Tenant LIST scoped by ownership path ``property.owned_by.user``."""
    own_tenant = TenantFactory(property=sample_property)
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_tenant = TenantFactory(property=other_property)
    resp = auth_client.get("/api/v1/tenants/")
    assert resp.status_code == 200
    ids = [t["id"] for t in _results(resp)]
    assert own_tenant.id in ids
    assert other_tenant.id not in ids


@pytest.mark.django_db
def test_create_tenant_rejects_other_landlords_property(auth_client, other_landlord_user):
    """POST /tenants/ with another landlord's ``property`` FK → 400/404.

    The ViewSet MUST validate that the client-supplied ``property``
    belongs to the requesting user before saving. Otherwise a client could
    file a Tenant against a Property they don't own — an IDOR.
    """
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    payload = {
        "property": other_property.id,  # Attempted IDOR
        "first_name": "Sneaky",
        "last_name": "Tenant",
        "phone": "555-0001",
        "lease_start": "2024-01-01",
    }
    resp = auth_client.post("/api/v1/tenants/", payload, content_type="application/json")
    # 400 (validation) or 404 (scoped property lookup) — both block the write.
    assert resp.status_code in (400, 404), resp.content
    # Confirm no tenant row was actually persisted.
    from rentals.models import Tenant
    assert not Tenant.objects.filter(first_name="Sneaky").exists()


@pytest.mark.django_db
def test_create_tenant_assigns_to_own_property(auth_client, sample_property):
    """POST /tenants/ with the caller's own ``property`` → 201, persisted."""
    payload = {
        "property": sample_property.id,
        "first_name": "Alice",
        "last_name": "Tenant",
        "phone": "555-0100",
        "lease_start": "2024-01-01",
    }
    resp = auth_client.post("/api/v1/tenants/", payload, content_type="application/json")
    assert resp.status_code == 201, resp.content
    assert resp.json()["property"] == sample_property.id


@pytest.mark.django_db
def test_transaction_list_excludes_other_landlords(auth_client, sample_property, other_landlord_user):
    """Transaction LIST scoped by ``property.owned_by.user``."""
    own_txn = TransactionFactory(property=sample_property)
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_txn = TransactionFactory(property=other_property)
    resp = auth_client.get("/api/v1/transactions/")
    assert resp.status_code == 200
    ids = [t["id"] for t in _results(resp)]
    assert own_txn.id in ids
    assert other_txn.id not in ids


@pytest.mark.django_db
def test_create_transaction_rejects_other_landlords_property(
    auth_client, other_landlord_user
):
    """POST /transactions/ with another landlord's ``property`` → 400."""
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    payload = {
        "date": "2024-01-15",
        "property": other_property.id,  # Attempted IDOR
        "tenant": None,
        "category": "rent",
        "period": "2024-01",
        "currency": "USD",
        "amount": "1000.00",
    }
    resp = auth_client.post(
        "/api/v1/transactions/", payload, content_type="application/json"
    )
    # 400 (field-level validation error) or 404 (scoped queryset lookup
    # rejects the foreign PK) — either is acceptable per the brief; what
    # matters is the cross-landlord write must NOT succeed.
    assert resp.status_code in (400, 404), resp.content
    from rentals.models import Transaction
    # Assert no Transaction with the posted ``period``+``amount`` was
    # persisted. (Previously this checked ``comment__contains="Sneaky"``
    # but the payload never set ``comment`` — the assertion was vacuous.)
    assert not Transaction.objects.filter(
        period="2024-01", amount="1000.00"
    ).exists()


@pytest.mark.django_db
def test_create_transaction_rejects_other_landlords_tenant(
    auth_client, sample_property, other_landlord_user
):
    """POST /transactions/ with another landlord's ``tenant`` FK → 400.

    Transaction has BOTH ``property`` and ``tenant`` FKs that must be
    validated against the requester. The ViewSet must catch a mismatch
    even when ``property`` is valid but ``tenant`` belongs to a different
    landlord (cross-property hijack).
    """
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_tenant = TenantFactory(property=other_property)
    payload = {
        "date": "2024-01-15",
        "property": sample_property.id,  # Own property...
        "tenant": other_tenant.id,  # ...but other landlord's tenant
        "category": "rent",
        "period": "2024-01",
        "currency": "USD",
        "amount": "1000.00",
    }
    resp = auth_client.post(
        "/api/v1/transactions/", payload, content_type="application/json"
    )
    assert resp.status_code == 400, resp.content


@pytest.mark.django_db
def test_fx_list_returns_200(auth_client):
    """FX list endpoint wired and reachable (no ownership scoping on FX)."""
    FXFactory()
    resp = auth_client.get("/api/v1/fx/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_chart_data_endpoint_requires_auth(db, client, sample_property):
    """Unauthenticated chart-data request → 401/403."""
    resp = client.get(
        "/api/v1/chart-data/",
        {"type": "property", "id": sample_property.id, "freq": "M",
         "start": "2024-01-01", "end": "2024-12-31", "currency": "USD"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_chart_data_endpoint_returns_payload(auth_client, sample_property):
    """GET /api/v1/chart-data/?type=property&id=<id>&freq=M&...

    Returns the chart payload shape from
    ``services.charts.get_chart_data`` via ``ChartDataResponseSerializer``.
    """
    # ``property`` branch needs at least one capital-structure row for
    # property_value() to produce a number; a single row is enough.
    from rentals.tests.factories import PropertyCapitalStructureFactory
    from datetime import date as _date
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=_date(2024, 1, 1),
        capital_structure_value=Decimal("100000"),
        capital_structure_debt=Decimal("40000"),
    )

    resp = auth_client.get(
        "/api/v1/chart-data/",
        {
            "type": "property",
            "id": sample_property.id,
            "freq": "M",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "currency": "USD",
        },
    )
    assert resp.status_code == 200, resp.content
    payload = resp.json()
    # Property branch: 2 datasets (Debt, Equity), currency ends with 'k'.
    assert "datasets" in payload
    assert [d["label"] for d in payload["datasets"]] == ["Debt", "Equity"]
    assert payload["currency"].endswith("k")


@pytest.mark.django_db
def test_chart_data_endpoint_rejects_other_landlords_property(
    auth_client, other_landlord_user
):
    """Chart-data for another landlord's property → 404 (ownership validated).

    The endpoint MUST validate the referenced entity belongs to the
    requester, otherwise it leaks capital/datasets cross-tenant.
    """
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    resp = auth_client.get(
        "/api/v1/chart-data/",
        {
            "type": "property",
            "id": other_property.id,
            "freq": "M",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "currency": "USD",
        },
    )
    assert resp.status_code == 404, resp.content


# ---------------------------------------------------------------------------
# Regression tests: PATCH partial-update and non-landlord Property create
# ---------------------------------------------------------------------------
#
# These tests pin behavior that was previously broken:
#
# * PATCH (partial_update) on Tenant/Transaction used to 400 when an
#   unchanged ownership FK (``property`` / ``tenant``) was omitted from
#   the payload, because the ViewSet treated a missing FK as a missing
#   value. The fix falls back to the existing instance value.
# * POST /properties/ from a non-landlord authenticated user (e.g. a
#   tenant-role user) used to raise ``Landlord.DoesNotExist`` (500). The
#   fix wraps the lookup and returns 403.


@pytest.mark.django_db
def test_patch_tenant_without_property_succeeds(auth_client, sample_property):
    """PATCH /tenants/<id>/ updating only ``phone`` -> 200, phone updated.

    Regression for the partial-update bug: ``TenantViewSet._validate_and_save``
    previously treated a missing ``property`` in ``validated_data`` (always
    the case on PATCH when ``property`` is unchanged) as a missing required
    field and raised 400. The fix falls back to the instance's existing
    ``property``.
    """
    tenant = TenantFactory(
        property=sample_property,
        first_name="PatchMe",
        last_name="Tenant",
        phone="555-0000",
    )
    resp = auth_client.patch(
        f"/api/v1/tenants/{tenant.id}/",
        {"phone": "555-9999"},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["phone"] == "555-9999"
    tenant.refresh_from_db()
    assert tenant.phone == "555-9999"
    # ``property`` is unchanged.
    assert tenant.property_id == sample_property.id


@pytest.mark.django_db
def test_patch_transaction_without_property_succeeds(auth_client, sample_property):
    """PATCH /transactions/<id>/ updating only ``comment`` -> 200.

    Regression for the partial-update bug on Transaction: same shape as
    the Tenant case. ``property`` and ``tenant`` are both omitted from
    the PATCH body; the ViewSet must fall back to the existing instance
    values rather than raising 400.
    """
    txn = TransactionFactory(
        property=sample_property,
        amount=Decimal("1500.00"),
        comment="Original",
    )
    resp = auth_client.patch(
        f"/api/v1/transactions/{txn.id}/",
        {"comment": "Updated comment"},
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["comment"] == "Updated comment"
    txn.refresh_from_db()
    assert txn.comment == "Updated comment"
    # ``property`` is unchanged.
    assert txn.property_id == sample_property.id


@pytest.mark.django_db
def test_property_create_rejects_non_landlord_with_403(db):
    """POST /properties/ from a non-landlord user -> 403 (not 500).

    Regression: ``PropertyViewSet._force_owner`` previously dereferenced
    ``request.user.landlord`` unconditionally, which raises
    ``Landlord.DoesNotExist`` (500) for an authenticated user with no
    Landlord row (e.g. a tenant-role user, or any non-landlord account).
    The fix catches that and raises ``PermissionDenied`` (403).

    The payload includes a valid ``owned_by`` PK only to satisfy the
    serializer's required-field check — what we are testing is that the
    view layer (``_force_owner``) refuses the call before save, not the
    serializer's input validation.
    """
    from rentals.tests.factories import UserFactory

    non_landlord = UserFactory(is_landlord=False, is_tenant=False)
    from rentals.models import Landlord
    assert not Landlord.objects.filter(user=non_landlord).exists()

    # Any landlord PK to pass serializer validation; the ViewSet must
    # reject the request before save regardless of this value.
    other_landlord = UserFactory(is_landlord=True).landlord

    c = Client()
    c.force_login(non_landlord)
    payload = {
        "owned_by": other_landlord.id,
        "name": "Should Not Be Created",
        "location": "Nowhere",
        "num_bedrooms": 2,
        "currency": "USD",
    }
    resp = c.post("/api/v1/properties/", payload, content_type="application/json")
    assert resp.status_code == 403, resp.content
    from rentals.models import Property
    assert not Property.objects.filter(name="Should Not Be Created").exists()


# ---------------------------------------------------------------------------
# Task 5: /api/v1/property-valuations/ — last CRUD endpoint to retire
# handle_element (the legacy view's ``data_type='propertyValuation'`` branch).
# ---------------------------------------------------------------------------
#
# Same per-user-scoped ModelViewSet pattern as Phase 1 Task 17:
# ``get_queryset`` filters by ``property__owned_by__user=request.user`` and
# ``perform_create`` validates the client-supplied ``property`` FK belongs to
# the requester before saving.


@pytest.mark.django_db
def test_property_valuation_list_requires_auth(db, client):
    resp = client.get("/api/v1/property-valuations/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_property_valuation_list_returns_only_own(auth_client, sample_property):
    from rentals.tests.factories import PropertyCapitalStructureFactory
    val = PropertyCapitalStructureFactory(property=sample_property)
    resp = auth_client.get("/api/v1/property-valuations/")
    assert resp.status_code == 200
    assert any(v["id"] == val.id for v in resp.json())


@pytest.mark.django_db
def test_property_valuation_create_validates_property_ownership(auth_client, sample_property, other_landlord_user):
    from django.test import Client
    from rentals.tests.factories import PropertyFactory
    other_prop = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    resp = other_client.post("/api/v1/property-valuations/", {
        "property": sample_property.id,
        "capital_structure_date": "2024-01-01",
        "capital_structure_value": "250000.00",
        "capital_structure_debt": "150000.00",
    }, content_type="application/json")
    assert resp.status_code == 400  # property doesn't belong to requester


# ---------------------------------------------------------------------------
# Task 7: @action endpoints — tenant vacate + FX update
# ---------------------------------------------------------------------------
#
# Two ``@action`` endpoints wiring the last behavioral mutations the
# React SPA needs into ``/api/v1/``:
#
# * ``POST /api/v1/tenants/<id>/vacate/`` — sets ``lease_end`` on a tenant
#   via the ViewSet's ``get_object()`` so ownership scoping applies (an
#   out-of-scope PK is 404, never 403 — same enumeration defense as the
#   rest of the API).
# * ``POST /api/v1/fx/update/`` — wraps ``services.fx.update_rates`` (which
#   itself wraps yfinance). The endpoint loops over the requester's own
#   properties (mirroring the legacy ``update_fx_view`` semantics). The
#   service is mocked in the test — no network calls.


@pytest.mark.django_db
def test_vacate_tenant_sets_lease_end(auth_client, sample_property):
    """POST /tenants/<id>/vacate/ with ``{lease_end}`` -> 200, tenant's
    ``lease_end`` is persisted.

    The vacate action is a thin mutation that delegates ownership scoping
    to ``self.get_object()`` — the same scoped ``get_queryset`` that LIST
    and RETRIEVE use — so the same per-user isolation applies (the second
    test pins the cross-landlord 404 path).
    """
    from rentals.tests.factories import TenantFactory
    from rentals.models import Tenant
    tenant = TenantFactory(property=sample_property)
    resp = auth_client.post(
        f"/api/v1/tenants/{tenant.id}/vacate/",
        {"lease_end": "2024-12-31"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    tenant.refresh_from_db()
    assert str(tenant.lease_end) == "2024-12-31"


@pytest.mark.django_db
def test_vacate_tenant_other_landlord_404(
    auth_client, sample_property, other_landlord_user
):
    """POST /tenants/<other_pk>/vacate/ -> 404 (not 403, not 200).

    Because ``vacate`` resolves the tenant via ``self.get_object()`` (which
    uses the per-user scoped queryset), a tenant owned by another landlord
    simply does not exist from this caller's perspective. No enumeration
    channel.
    """
    from rentals.tests.factories import TenantFactory, PropertyFactory
    other_prop = PropertyFactory(owned_by=other_landlord_user.landlord)
    other_tenant = TenantFactory(property=other_prop)
    resp = auth_client.post(
        f"/api/v1/tenants/{other_tenant.id}/vacate/",
        {"lease_end": "2024-12-31"},
        content_type="application/json",
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_fx_update_endpoint(auth_client, sample_property):
    """POST /fx/update/ -> 200 ``{detail: "FX rates updated"}`` and
    ``services.fx.update_rates`` was invoked (mocked — no network).

    The endpoint wraps ``services.fx.update_rates`` for each of the
    requester's properties (mirroring the legacy ``update_fx_view``).
    Asserting the service was called rather than asserting a specific
    property_id keeps the test decoupled from the iteration order.

    Note: ``sample_property`` is needed because the real
    ``update_rates`` signature takes a ``property_id`` (not a user), so
    the endpoint loops the caller's properties — with no properties the
    loop body would not run and the service would never be called.
    """
    from unittest.mock import patch
    with patch("rentals.services.fx.update_rates") as mock_update:
        resp = auth_client.post("/api/v1/fx/update/")
        assert resp.status_code == 200
        assert mock_update.called
