"""Security-deposit service: the only write path for ``DepositMovement``.

Every write runs in ``transaction.atomic()`` and validates the tenant's
post-change movement list (built in memory) before touching the database.
"""

import copy
from collections import defaultdict
from decimal import Decimal

from django.db import transaction as db_transaction

from rentals.constants import DEPOSIT_APPLICATION_CATEGORIES
from rentals.financial_semantics import deposit_signed_amount
from rentals.models import DepositMovement, Tenant, Transaction

APPLIED_COMMENT = "Applied from security deposit"
_UPDATABLE = {"date", "currency", "amount", "applied_to", "transaction", "comment", "kind"}


class DepositRuleError(Exception):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message


def _replay_key(m):
    return (m.date, 0 if m.kind == "received" else 1, m.id or 0)


# --- validation -----------------------------------------------------------

def _check_shape(m):
    """Rules 7 and applied-specific field requirements."""
    if m.kind == "applied":
        if not m.applied_to:
            raise DepositRuleError("applied_to", "applied_to is required for an applied movement.")
        if m.applied_to not in DEPOSIT_APPLICATION_CATEGORIES:
            raise DepositRuleError("applied_to", "A deposit can only be applied to rent or cost reimbursement.")
    else:
        if m.applied_to:
            raise DepositRuleError("applied_to", "applied_to is only allowed on an applied movement.")
        if m.transaction_id:
            raise DepositRuleError("transaction", "transaction is only allowed on an applied movement.")
    if m.amount is None or m.amount <= 0:
        raise DepositRuleError("amount", "Amount must be greater than zero.")


def _check_currency(movements):
    """Rule 1: one currency across the tenant's movements."""
    currencies = {m.currency for m in movements}
    if len(currencies) > 1:
        raise DepositRuleError("currency", "All deposit movements for a tenant must use the same currency.")


def _check_no_overdraw(movements):
    """Rule 2: replayed running balance never goes below zero."""
    balance = Decimal("0")
    for m in sorted(movements, key=_replay_key):
        balance += deposit_signed_amount(m.kind, m.amount)
        if balance < 0:
            raise DepositRuleError("amount", "Deposit balance cannot go below zero.")


def _check_attach(m):
    """Rule 4: an attached transaction must match the movement."""
    tx = m.transaction
    if tx.tenant_id != m.tenant_id:
        raise DepositRuleError("transaction", "Transaction belongs to a different tenant.")
    if tx.category != m.applied_to:
        raise DepositRuleError("transaction", "Transaction category does not match applied_to.")
    if tx.currency != m.currency:
        raise DepositRuleError("transaction", "Transaction currency does not match the deposit currency.")
    if tx.date != m.date:
        raise DepositRuleError("transaction", "Transaction date does not match the movement date.")
    if abs(tx.amount) < m.amount:
        raise DepositRuleError("amount", "Amount exceeds the linked transaction amount.")
    linked = DepositMovement.objects.filter(transaction=tx)
    if m.pk:
        linked = linked.exclude(pk=m.pk)
    if linked.exists():
        raise DepositRuleError("transaction", "Transaction is already linked to another deposit movement.")


def _validate(candidate, others):
    _check_shape(candidate)
    movements = list(others) + [candidate]
    _check_currency(movements)
    _check_no_overdraw(movements)
    if candidate.kind == "applied" and candidate.transaction_id and not candidate.owns_transaction:
        _check_attach(candidate)


# --- writes ---------------------------------------------------------------

def _lock_tenant(tenant):
    return Tenant.objects.select_for_update().get(pk=tenant.pk)


def create_movement(tenant, *, date, kind, currency, amount, applied_to=None, transaction=None, comment=None):
    with db_transaction.atomic():
        tenant = _lock_tenant(tenant)
        movement = DepositMovement(
            tenant=tenant, date=date, kind=kind, currency=currency, amount=amount,
            applied_to=applied_to, transaction=transaction, comment=comment,
        )
        _validate(movement, tenant.deposit_movements.all())
        if kind == "applied" and transaction is None:
            movement.transaction = Transaction.objects.create(
                property=tenant.property, tenant=tenant, category=applied_to,
                date=date, currency=currency, amount=amount, comment=APPLIED_COMMENT,
            )
            movement.owns_transaction = True
        movement.save()
        return movement


def update_movement(movement, **fields):
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise TypeError(f"Unknown fields: {sorted(unknown)}")
    if "kind" in fields and fields["kind"] != movement.kind and "applied" in (fields["kind"], movement.kind):
        raise DepositRuleError("kind", "Cannot change a movement to or from 'applied'; delete and re-add instead.")

    with db_transaction.atomic():
        tenant = _lock_tenant(movement.tenant)
        current = DepositMovement.objects.select_related("transaction").get(pk=movement.pk)
        candidate = copy.copy(current)
        for name, value in fields.items():
            setattr(candidate, name, value)
        if "transaction" in fields:
            if current.owns_transaction and fields["transaction"] != current.transaction:
                raise DepositRuleError("transaction", "Cannot relink a movement that owns its transaction.")
            if current.kind == "applied" and fields["transaction"] is None and not current.owns_transaction:
                raise DepositRuleError("transaction", "An applied movement must keep a linked transaction.")

        others = tenant.deposit_movements.exclude(pk=current.pk)
        _validate(candidate, others)

        if current.owns_transaction:
            tx = current.transaction
            tx.date = candidate.date
            tx.amount = candidate.amount
            tx.category = candidate.applied_to
            tx.currency = candidate.currency
            tx.save()
            candidate.transaction = tx
        candidate.save()

        for name in fields:
            setattr(movement, name, getattr(candidate, name))
        movement.transaction = candidate.transaction
        return candidate


def delete_movement(movement):
    with db_transaction.atomic():
        tenant = _lock_tenant(movement.tenant)
        current = DepositMovement.objects.select_related("transaction").get(pk=movement.pk)
        _check_no_overdraw(list(tenant.deposit_movements.exclude(pk=current.pk)))
        tx = current.transaction if current.owns_transaction else None
        current.delete()
        if tx is not None:
            tx.delete()


# --- reads ----------------------------------------------------------------

def _balances(movements):
    totals = defaultdict(lambda: Decimal("0"))
    for m in movements:
        totals[m.currency] += deposit_signed_amount(m.kind, m.amount)
    return dict(totals)


def deposit_held(*, as_of, tenant=None, property=None):
    if (tenant is None) == (property is None):
        raise ValueError("Pass exactly one of tenant or property.")
    qs = DepositMovement.objects.filter(date__lte=as_of)
    qs = qs.filter(tenant=tenant) if tenant is not None else qs.filter(tenant__property=property)
    return _balances(qs)


def deposit_held_by_tenant(*, property, as_of):
    per_tenant = defaultdict(list)
    qs = (
        DepositMovement.objects.filter(tenant__property=property, date__lte=as_of)
        .select_related("tenant")
        .order_by("tenant_id", "date", "id")
    )
    tenants = {}
    for m in qs:
        tenants[m.tenant_id] = m.tenant
        per_tenant[m.tenant_id].append(m)
    rows = []
    for tenant_id in sorted(per_tenant):
        for currency, balance in _balances(per_tenant[tenant_id]).items():
            rows.append((tenants[tenant_id], currency, balance))
    return rows


def movements_for_user(user, *, start=None, end=None, property_ids=(), tenant_id=None):
    qs = DepositMovement.objects.filter(tenant__property__owned_by__user=user).select_related("tenant__property")
    if start is not None:
        qs = qs.filter(date__gte=start)
    if end is not None:
        qs = qs.filter(date__lte=end)
    if property_ids:
        qs = qs.filter(tenant__property_id__in=list(property_ids))
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)
    return qs
