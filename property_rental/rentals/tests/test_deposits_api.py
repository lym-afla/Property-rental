"""API tests for tenant security deposits (guards on deposit-linked transactions)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from rentals.models import Transaction
from rentals.services.deposits import create_movement
from rentals.tests.factories import TenantFactory, TransactionFactory

CONFLICT_DETAIL = "Edit the security deposit movement instead."


@pytest.fixture
def tenant(sample_property):
    return TenantFactory(property=sample_property)


@pytest.fixture
def applied_movement(tenant):
    """An applied movement that owns a rent transaction (deposit received first)."""
    create_movement(
        tenant, date=date(2026, 1, 1), kind="received", currency="USD", amount=Decimal("1000.00")
    )
    return create_movement(
        tenant,
        date=date(2026, 2, 1),
        kind="applied",
        currency="USD",
        amount=Decimal("400.00"),
        applied_to="rent",
    )


def _patch(client, pk, payload):
    return client.patch(
        f"/api/v1/transactions/{pk}/", json.dumps(payload), content_type="application/json"
    )


@pytest.mark.django_db
def test_transaction_payload_exposes_deposit_movement(auth_client, sample_property, applied_movement):
    linked = auth_client.get(f"/api/v1/transactions/{applied_movement.transaction_id}/")
    assert linked.status_code == 200
    assert linked.json()["deposit_movement"] == applied_movement.id

    plain = TransactionFactory(property=sample_property)
    unlinked = auth_client.get(f"/api/v1/transactions/{plain.id}/")
    assert unlinked.status_code == 200
    assert unlinked.json()["deposit_movement"] is None


@pytest.mark.django_db
def test_delete_linked_transaction_returns_409(auth_client, applied_movement):
    pk = applied_movement.transaction_id
    response = auth_client.delete(f"/api/v1/transactions/{pk}/")
    assert response.status_code == 409
    assert response.json() == {"detail": CONFLICT_DETAIL}
    assert Transaction.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_patch_amount_on_linked_transaction_returns_409(auth_client, applied_movement):
    pk = applied_movement.transaction_id
    response = _patch(auth_client, pk, {"amount": "999.00"})
    assert response.status_code == 409
    assert response.json() == {"detail": CONFLICT_DETAIL}
    assert Transaction.objects.get(pk=pk).amount == Decimal("400.00")


@pytest.mark.django_db
def test_patch_comment_on_linked_transaction_allowed(auth_client, applied_movement):
    pk = applied_movement.transaction_id
    response = _patch(auth_client, pk, {"comment": "Edited note"})
    assert response.status_code == 200
    assert Transaction.objects.get(pk=pk).comment == "Edited note"


@pytest.mark.django_db
def test_put_with_unchanged_guarded_fields_and_new_comment_allowed(auth_client, applied_movement):
    tx = applied_movement.transaction
    payload = {
        "date": tx.date.isoformat(),
        "property": tx.property_id,
        "tenant": tx.tenant_id,
        "category": tx.category,
        "period": tx.period,
        "currency": tx.currency,
        "amount": str(tx.amount),
        "comment": "Resent with note",
    }
    response = auth_client.put(
        f"/api/v1/transactions/{tx.pk}/", json.dumps(payload), content_type="application/json"
    )
    assert response.status_code == 200, response.content
    assert Transaction.objects.get(pk=tx.pk).comment == "Resent with note"


@pytest.mark.django_db
def test_patch_unlinked_transaction_amount_still_allowed(auth_client, sample_property):
    plain = TransactionFactory(property=sample_property, category="rent", currency="USD")
    response = _patch(auth_client, plain.pk, {"amount": "123.00"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_transaction_list_query_count_does_not_grow_with_rows(
    auth_client, sample_property, applied_movement
):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as one:
        assert auth_client.get("/api/v1/transactions/").status_code == 200
    for _ in range(3):
        TransactionFactory(property=sample_property)
    with CaptureQueriesContext(connection) as many:
        assert auth_client.get("/api/v1/transactions/").status_code == 200
    assert len(many) == len(one)
