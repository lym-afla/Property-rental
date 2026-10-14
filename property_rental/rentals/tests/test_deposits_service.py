from datetime import date
from decimal import Decimal

import pytest
from django.db.models import RestrictedError

from rentals.models import DepositMovement, Transaction
from rentals.services.deposits import (
    DepositRuleError,
    create_movement,
    delete_movement,
    deposit_held,
    deposit_held_by_tenant,
    movements_for_user,
    update_movement,
)
from rentals.tests.factories import PropertyFactory, TenantFactory, TransactionFactory

pytestmark = pytest.mark.django_db

D = date.fromisoformat


@pytest.fixture
def tenant(sample_property):
    return TenantFactory(property=sample_property, lease_start=date(2025, 1, 1))


def rcv(tenant, amt, d="2025-01-01", currency="GBP"):
    return create_movement(tenant, date=D(d), kind="received", currency=currency, amount=Decimal(amt))


def out(tenant, kind, amt, d, **kw):
    return create_movement(tenant, date=D(d), kind=kind, currency="GBP", amount=Decimal(amt), **kw)


def test_receive_partial_return_balance(tenant):
    rcv(tenant, "1500")
    out(tenant, "returned", "500", "2025-06-01")
    assert deposit_held(tenant=tenant, as_of=date(2025, 5, 31)) == {"GBP": Decimal("1500")}
    assert deposit_held(tenant=tenant, as_of=date(2025, 6, 1)) == {"GBP": Decimal("1000")}
    assert deposit_held(tenant=tenant, as_of=date(2024, 12, 31)) == {}


def test_deposit_held_requires_exactly_one_scope(tenant, sample_property):
    with pytest.raises(ValueError):
        deposit_held(as_of=date(2025, 1, 1))
    with pytest.raises(ValueError):
        deposit_held(as_of=date(2025, 1, 1), tenant=tenant, property=sample_property)


def test_currency_locked_to_existing_movements(tenant):
    rcv(tenant, "1000")
    with pytest.raises(DepositRuleError) as e:
        rcv(tenant, "100", currency="EUR")
    assert e.value.field == "currency"
    assert DepositMovement.objects.count() == 1


def test_currency_of_only_movement_can_change(tenant):
    m = rcv(tenant, "1000")
    update_movement(m, currency="EUR")
    m.refresh_from_db()
    assert m.currency == "EUR"


def test_currency_change_rejected_when_other_movements_exist(tenant):
    m = rcv(tenant, "1000")
    out(tenant, "returned", "100", "2025-02-01")
    with pytest.raises(DepositRuleError) as e:
        update_movement(m, currency="EUR")
    assert e.value.field == "currency"


def test_return_cannot_exceed_held(tenant):
    rcv(tenant, "1000")
    with pytest.raises(DepositRuleError) as e:
        out(tenant, "returned", "1000.01", "2025-02-01")
    assert e.value.field == "amount"


def test_outflow_before_receipt_rejected(tenant):
    rcv(tenant, "1000", "2025-03-01")
    with pytest.raises(DepositRuleError) as e:
        out(tenant, "returned", "100", "2025-02-01")
    assert e.value.field == "amount"


def test_same_day_receipt_and_application_allowed(tenant):
    rcv(tenant, "1000")
    out(tenant, "applied", "1000", "2025-01-01", applied_to="rent")
    assert deposit_held(tenant=tenant, as_of=date(2025, 1, 1)) == {"GBP": Decimal("0")}


def test_same_day_receipt_orders_before_outflow_regardless_of_id(tenant):
    r1 = rcv(tenant, "1000")
    out(tenant, "applied", "1000", "2025-01-01", applied_to="rent")
    rcv(tenant, "1000")  # larger id than the application, same date
    update_movement(r1, date=D("2025-02-01"))
    r1.refresh_from_db()
    assert r1.date == date(2025, 2, 1)


def test_received_returned_kind_change_allowed_when_balance_permits(tenant):
    rcv(tenant, "1000")
    later = rcv(tenant, "500", "2025-02-01")
    update_movement(later, kind="returned")
    later.refresh_from_db()
    assert later.kind == "returned"
    assert deposit_held(tenant=tenant, as_of=date(2025, 3, 1)) == {"GBP": Decimal("500")}


def test_kind_change_rejected_when_it_would_overdraw(tenant):
    first = rcv(tenant, "1000")
    with pytest.raises(DepositRuleError) as e:
        update_movement(first, kind="returned")
    assert e.value.field == "amount"
    assert DepositMovement.objects.get(pk=first.pk).kind == "received"


def test_shrinking_receipt_below_applied_rejected(tenant):
    receipt = rcv(tenant, "1000")
    out(tenant, "applied", "800", "2025-02-01", applied_to="rent")
    with pytest.raises(DepositRuleError) as e:
        update_movement(receipt, amount=Decimal("700"))
    assert e.value.field == "amount"
    assert DepositMovement.objects.get(pk=receipt.pk).amount == Decimal("1000")


def test_deleting_receipt_needed_by_later_outflow_rejected(tenant):
    receipt = rcv(tenant, "1000")
    out(tenant, "returned", "100", "2025-02-01")
    with pytest.raises(DepositRuleError) as e:
        delete_movement(receipt)
    assert e.value.field == "amount"
    assert DepositMovement.objects.count() == 2


def test_apply_create_mode_creates_owned_rent_transaction(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    assert m.owns_transaction
    t = m.transaction
    assert t.category == "rent"
    assert t.amount == Decimal("1500")
    assert t.tenant == tenant
    assert t.property == tenant.property
    assert t.currency == "GBP"
    assert t.comment == "Applied from security deposit"
    assert t.date == date(2025, 12, 1)


def test_apply_cost_reimbursement_creates_positive_contra_expense(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "200", "2025-12-01", applied_to="cost_reimbursement")
    assert m.transaction.amount == Decimal("200")
    assert m.transaction.type == "expense"


def _rent_row(tenant, **kw):
    params = dict(property=tenant.property, tenant=tenant, category="rent", amount=Decimal("1500"),
                  currency="GBP", date=date(2025, 12, 1))
    params.update(kw)
    return TransactionFactory(**params)


def test_apply_attach_mode_links_existing_row(tenant):
    rcv(tenant, "2000")
    row = _rent_row(tenant)
    before = Transaction.objects.count()
    m = out(tenant, "applied", "500", "2025-12-01", applied_to="rent", transaction=row)
    assert not m.owns_transaction
    assert m.transaction == row
    assert Transaction.objects.count() == before


@pytest.mark.parametrize(
    "case,field",
    [
        ("other_tenant", "transaction"),
        ("category", "transaction"),
        ("currency", "transaction"),
        ("date", "transaction"),
        ("amount", "amount"),
        ("linked", "transaction"),
    ],
)
def test_attach_rejects_mismatch(tenant, case, field):
    rcv(tenant, "5000")
    amount = "500"
    if case == "other_tenant":
        row = _rent_row(TenantFactory(property=tenant.property, lease_start=date(2025, 1, 1)))
    elif case == "category":
        row = _rent_row(tenant, category="utilities")
    elif case == "currency":
        row = _rent_row(tenant, currency="EUR")
    elif case == "date":
        row = _rent_row(tenant, date=date(2025, 12, 2))
    elif case == "amount":
        row = _rent_row(tenant)
        amount = "1500.01"
    else:
        row = _rent_row(tenant)
        out(tenant, "applied", "100", "2025-12-01", applied_to="rent", transaction=row)
    count = DepositMovement.objects.count()
    with pytest.raises(DepositRuleError) as e:
        out(tenant, "applied", amount, "2025-12-01", applied_to="rent", transaction=row)
    assert e.value.field == field
    assert DepositMovement.objects.count() == count


def test_attach_revalidated_on_update(tenant):
    rcv(tenant, "5000")
    row = _rent_row(tenant)
    m = out(tenant, "applied", "500", "2025-12-01", applied_to="rent", transaction=row)
    with pytest.raises(DepositRuleError) as e:
        update_movement(m, amount=Decimal("1600"))
    assert e.value.field == "amount"
    update_movement(m, amount=Decimal("1500"))
    m.refresh_from_db()
    assert m.amount == Decimal("1500")


def test_update_owned_application_syncs_transaction(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    update_movement(m, amount=Decimal("1200"), date=D("2025-12-05"), applied_to="cost_reimbursement")
    t = Transaction.objects.get(pk=m.transaction_id)
    assert t.amount == Decimal("1200")
    assert t.date == date(2025, 12, 5)
    assert t.category == "cost_reimbursement"
    assert t.type == "expense"


def test_update_rejection_leaves_db_untouched(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    with pytest.raises(DepositRuleError):
        update_movement(m, amount=Decimal("2500"))
    assert DepositMovement.objects.get(pk=m.pk).amount == Decimal("1500")
    assert Transaction.objects.get(pk=m.transaction_id).amount == Decimal("1500")


def test_delete_owned_application_deletes_transaction(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    tx_id = m.transaction_id
    delete_movement(m)
    assert not Transaction.objects.filter(pk=tx_id).exists()
    assert DepositMovement.objects.count() == 1


def test_delete_attached_application_keeps_transaction(tenant):
    rcv(tenant, "2000")
    row = _rent_row(tenant)
    m = out(tenant, "applied", "500", "2025-12-01", applied_to="rent", transaction=row)
    delete_movement(m)
    assert Transaction.objects.filter(pk=row.pk).exists()


def test_kind_change_to_or_from_applied_rejected(tenant):
    receipt = rcv(tenant, "2000")
    applied = out(tenant, "applied", "100", "2025-12-01", applied_to="rent")
    with pytest.raises(DepositRuleError) as e:
        update_movement(receipt, kind="applied")
    assert e.value.field == "kind"
    with pytest.raises(DepositRuleError) as e:
        update_movement(applied, kind="returned")
    assert e.value.field == "kind"


def test_non_applied_rejects_applied_to_and_transaction(tenant):
    row = _rent_row(tenant)
    with pytest.raises(DepositRuleError) as e:
        create_movement(tenant, date=D("2025-01-01"), kind="received", currency="GBP",
                        amount=Decimal("1"), applied_to="rent")
    assert e.value.field == "applied_to"
    with pytest.raises(DepositRuleError) as e:
        create_movement(tenant, date=D("2025-01-01"), kind="received", currency="GBP",
                        amount=Decimal("1"), transaction=row)
    assert e.value.field == "transaction"


def test_applied_requires_applied_to(tenant):
    rcv(tenant, "100")
    with pytest.raises(DepositRuleError) as e:
        out(tenant, "applied", "50", "2025-02-01")
    assert e.value.field == "applied_to"


def test_linked_transaction_cannot_be_deleted_directly(tenant):
    rcv(tenant, "2000")
    m = out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    with pytest.raises(RestrictedError):
        m.transaction.delete()


def test_tenant_delete_cascades_movements_and_owned_transactions(tenant):
    rcv(tenant, "2000")
    out(tenant, "applied", "1500", "2025-12-01", applied_to="rent")
    tenant.delete()
    assert DepositMovement.objects.count() == 0
    assert Transaction.objects.count() == 0


def test_property_balance_groups_currencies(tenant, sample_property):
    other = TenantFactory(property=sample_property, lease_start=date(2025, 1, 1))
    rcv(tenant, "1500")
    rcv(other, "900", currency="EUR")
    as_of = date(2025, 6, 1)
    assert deposit_held(property=sample_property, as_of=as_of) == {"GBP": Decimal("1500"), "EUR": Decimal("900")}
    rows = deposit_held_by_tenant(property=sample_property, as_of=as_of)
    assert rows == sorted(rows, key=lambda r: r[0].id)
    assert [(t.id, c, b) for t, c, b in rows] == [
        (tenant.id, "GBP", Decimal("1500")),
        (other.id, "EUR", Decimal("900")),
    ]


def test_fully_returned_currency_kept_with_zero(tenant, sample_property):
    rcv(tenant, "100")
    out(tenant, "returned", "100", "2025-02-01")
    assert deposit_held(tenant=tenant, as_of=date(2025, 3, 1)) == {"GBP": Decimal("0")}
    assert deposit_held(property=sample_property, as_of=date(2025, 3, 1)) == {"GBP": Decimal("0")}
    assert [(c, b) for _, c, b in deposit_held_by_tenant(property=sample_property, as_of=date(2025, 3, 1))] == [
        ("GBP", Decimal("0"))
    ]


def test_movements_for_user_is_owner_scoped(tenant, sample_property, landlord_user, other_landlord_user):
    mine_a = rcv(tenant, "100", "2025-01-01")
    mine_a2 = rcv(tenant, "100", "2025-06-01")
    p2 = PropertyFactory(owned_by=landlord_user.landlord)
    t2 = TenantFactory(property=p2, lease_start=date(2025, 1, 1))
    mine_b = rcv(t2, "100", "2025-03-01")
    foreign_t = TenantFactory(property=PropertyFactory(owned_by=other_landlord_user.landlord),
                              lease_start=date(2025, 1, 1))
    rcv(foreign_t, "100", "2025-03-01")

    ids = lambda qs: {m.pk for m in qs}
    assert ids(movements_for_user(landlord_user)) == {mine_a.pk, mine_a2.pk, mine_b.pk}
    assert ids(movements_for_user(landlord_user, property_ids=[p2.id])) == {mine_b.pk}
    assert ids(movements_for_user(landlord_user, tenant_id=tenant.id)) == {mine_a.pk, mine_a2.pk}
    assert ids(movements_for_user(landlord_user, start=D("2025-02-01"), end=D("2025-05-01"))) == {mine_b.pk}
    assert ids(movements_for_user(landlord_user, start=D("2025-01-01"), end=D("2025-01-01"))) == {mine_a.pk}
