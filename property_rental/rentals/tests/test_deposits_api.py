"""API tests for tenant security deposits (guards on deposit-linked transactions)."""

import json
from datetime import date
from decimal import Decimal

import pytest

from rentals.models import DepositMovement, Transaction
from rentals.services.deposits import create_movement
from rentals.tests.factories import PropertyFactory, TenantFactory, TransactionFactory

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


# --- deposit movements CRUD + balance ---------------------------------------

URL = "/api/v1/deposit-movements/"


def _post(client, payload):
    return client.post(URL, json.dumps(payload), content_type="application/json")


def _received(tenant, amount="1500.00", on=date(2026, 1, 1), currency="GBP"):
    return create_movement(
        tenant, date=on, kind="received", currency=currency, amount=Decimal(amount)
    )


@pytest.fixture
def other_tenant(other_landlord_user):
    return TenantFactory(property=PropertyFactory(owned_by=other_landlord_user.landlord))


@pytest.mark.django_db
def test_create_received_movement(auth_client, tenant):
    response = _post(
        auth_client,
        {"tenant": tenant.id, "date": "2026-01-01", "kind": "received", "currency": "GBP", "amount": "1500.00"},
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["owns_transaction"] is False
    assert body["transaction"] is None
    assert DepositMovement.objects.get(pk=body["id"]).tenant_id == tenant.id


@pytest.mark.django_db
def test_create_applied_movement_creates_owned_transaction(auth_client, tenant):
    _received(tenant)
    response = _post(
        auth_client,
        {"tenant": tenant.id, "date": "2026-02-01", "kind": "applied", "currency": "GBP",
         "amount": "400.00", "applied_to": "rent"},
    )
    assert response.status_code == 201, response.content
    assert response.json()["owns_transaction"] is True
    assert response.json()["transaction"] is not None


@pytest.mark.django_db
def test_list_filtered_by_tenant(auth_client, tenant, sample_property):
    mine = _received(tenant)
    other = TenantFactory(property=sample_property)
    _received(other, amount="200.00")
    response = auth_client.get(f"{URL}?tenant={tenant.id}")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [mine.id]


@pytest.mark.django_db
def test_list_filtered_by_property(auth_client, tenant, other_tenant):
    mine = _received(tenant)
    _received(other_tenant)
    response = auth_client.get(f"{URL}?property={tenant.property_id}")
    assert [row["id"] for row in response.json()] == [mine.id]


@pytest.mark.django_db
def test_list_excludes_other_landlords_movements(auth_client, tenant, other_tenant):
    mine = _received(tenant)
    _received(other_tenant)
    response = auth_client.get(URL)
    assert [row["id"] for row in response.json()] == [mine.id]


@pytest.mark.django_db
def test_other_landlords_movement_is_404(auth_client, other_tenant):
    theirs = _received(other_tenant)
    assert auth_client.get(f"{URL}{theirs.id}/").status_code == 404
    assert auth_client.delete(f"{URL}{theirs.id}/").status_code == 404


@pytest.mark.django_db
def test_patch_amount(auth_client, tenant):
    movement = _received(tenant)
    response = auth_client.patch(
        f"{URL}{movement.id}/", json.dumps({"amount": "1200.00"}), content_type="application/json"
    )
    assert response.status_code == 200, response.content
    assert response.json()["amount"] == "1200.00"
    movement.refresh_from_db()
    assert movement.amount == Decimal("1200.00")


@pytest.mark.django_db
def test_patch_same_tenant_ok_but_changing_tenant_rejected(auth_client, tenant, sample_property):
    movement = _received(tenant)
    same = auth_client.patch(
        f"{URL}{movement.id}/", json.dumps({"tenant": tenant.id}), content_type="application/json"
    )
    assert same.status_code == 200
    moved = TenantFactory(property=sample_property)
    response = auth_client.patch(
        f"{URL}{movement.id}/", json.dumps({"tenant": moved.id}), content_type="application/json"
    )
    assert response.status_code == 400
    assert "tenant" in response.json()
    movement.refresh_from_db()
    assert movement.tenant_id == tenant.id


@pytest.mark.django_db
def test_delete_movement(auth_client, tenant):
    movement = _received(tenant)
    response = auth_client.delete(f"{URL}{movement.id}/")
    assert response.status_code == 204
    assert not DepositMovement.objects.filter(pk=movement.id).exists()


@pytest.mark.django_db
def test_overdraw_returns_400_with_amount_error(auth_client, tenant):
    _received(tenant, amount="100.00")
    response = _post(
        auth_client,
        {"tenant": tenant.id, "date": "2026-02-01", "kind": "returned", "currency": "GBP", "amount": "500.00"},
    )
    assert response.status_code == 400
    assert response.json() == {"amount": ["Deposit balance cannot go below zero."]}
    assert DepositMovement.objects.filter(tenant=tenant).count() == 1


@pytest.mark.django_db
def test_invalid_kind_and_applied_to_are_400(auth_client, tenant):
    base = {"tenant": tenant.id, "date": "2026-01-01", "currency": "GBP", "amount": "10.00"}
    bad_kind = _post(auth_client, {**base, "kind": "bogus"})
    assert bad_kind.status_code == 400 and "kind" in bad_kind.json()
    bad_applied = _post(auth_client, {**base, "kind": "applied", "applied_to": "salary"})
    assert bad_applied.status_code == 400 and "applied_to" in bad_applied.json()


@pytest.mark.django_db
def test_cannot_create_for_other_landlords_tenant(auth_client, other_tenant):
    response = _post(
        auth_client,
        {"tenant": other_tenant.id, "date": "2026-01-01", "kind": "received", "currency": "GBP", "amount": "10.00"},
    )
    assert response.status_code == 400
    assert "tenant" in response.json()
    assert DepositMovement.objects.count() == 0


@pytest.mark.django_db
def test_cannot_attach_other_landlords_transaction(auth_client, tenant, other_tenant):
    _received(tenant)
    foreign = TransactionFactory(
        property=other_tenant.property, tenant=other_tenant, category="rent",
        currency="GBP", amount=Decimal("100.00"), date=date(2026, 2, 1),
    )
    response = _post(
        auth_client,
        {"tenant": tenant.id, "date": "2026-02-01", "kind": "applied", "currency": "GBP",
         "amount": "100.00", "applied_to": "rent", "transaction": foreign.id},
    )
    assert response.status_code == 400
    assert "transaction" in response.json()
    assert DepositMovement.objects.filter(kind="applied").count() == 0


@pytest.mark.django_db
def test_list_query_count_does_not_grow_with_rows(auth_client, tenant):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _received(tenant)
    with CaptureQueriesContext(connection) as one:
        assert auth_client.get(URL).status_code == 200
    for day in range(2, 5):
        _received(tenant, amount="10.00", on=date(2026, 1, day))
    with CaptureQueriesContext(connection) as many:
        assert auth_client.get(URL).status_code == 200
    assert len(many) == len(one)


@pytest.mark.django_db
def test_balance_by_tenant(auth_client, tenant):
    _received(tenant)
    create_movement(
        tenant, date=date(2026, 2, 1), kind="returned", currency="GBP", amount=Decimal("500.00")
    )
    response = auth_client.get(f"{URL}balance/?tenant={tenant.id}&as_of=2026-03-01")
    assert response.status_code == 200
    body = response.json()
    assert body["as_of"] == "2026-03-01"
    assert body["balances"] == [{"currency": "GBP", "amount": "1000.00"}]
    assert "by_tenant" not in body


@pytest.mark.django_db
def test_balance_by_property_includes_by_tenant(auth_client, tenant, sample_property):
    second = TenantFactory(property=sample_property)
    _received(tenant)
    _received(second, amount="250.50")
    response = auth_client.get(f"{URL}balance/?property={sample_property.id}&as_of=2026-03-01")
    assert response.status_code == 200
    body = response.json()
    assert body["balances"] == [{"currency": "GBP", "amount": "1750.50"}]
    assert sorted(body["by_tenant"], key=lambda r: r["tenant"]) == sorted(
        [
            {"tenant": tenant.id, "currency": "GBP", "amount": "1500.00"},
            {"tenant": second.id, "currency": "GBP", "amount": "250.50"},
        ],
        key=lambda r: r["tenant"],
    )


@pytest.mark.django_db
def test_balance_zero_balance_serialized(auth_client, tenant):
    _received(tenant)
    create_movement(
        tenant, date=date(2026, 2, 1), kind="returned", currency="GBP", amount=Decimal("1500.00")
    )
    body = auth_client.get(f"{URL}balance/?tenant={tenant.id}&as_of=2026-03-01").json()
    assert body["balances"] == [{"currency": "GBP", "amount": "0.00"}]


@pytest.mark.django_db
def test_balance_requires_exactly_one_scope(auth_client, tenant, sample_property):
    assert auth_client.get(f"{URL}balance/").status_code == 400
    both = auth_client.get(f"{URL}balance/?tenant={tenant.id}&property={sample_property.id}")
    assert both.status_code == 400


@pytest.mark.django_db
def test_balance_unowned_ids_404(auth_client, other_tenant):
    assert auth_client.get(f"{URL}balance/?tenant={other_tenant.id}").status_code == 404
    assert auth_client.get(f"{URL}balance/?property={other_tenant.property_id}").status_code == 404


@pytest.mark.django_db
def test_balance_respects_as_of(auth_client, tenant):
    _received(tenant, on=date(2026, 1, 1))
    _received(tenant, amount="300.00", on=date(2026, 6, 1))
    body = auth_client.get(f"{URL}balance/?tenant={tenant.id}&as_of=2026-03-01").json()
    assert body["balances"] == [{"currency": "GBP", "amount": "1500.00"}]
    body = auth_client.get(f"{URL}balance/?tenant={tenant.id}&as_of=2026-06-01").json()
    assert body["balances"] == [{"currency": "GBP", "amount": "1800.00"}]
