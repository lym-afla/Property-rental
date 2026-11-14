"""Read-only adapter from Rent's ledger to the Wealth v1.1 contract."""
import hashlib
import json
import re
from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from rentals.constants import TRANSACTION_CATEGORIES
from rentals.financial_semantics import deposit_signed_amount
from rentals.models import DepositMovement, OIDCIdentity, Property


class WealthExportError(ValueError):
    """Source data cannot be faithfully represented in Wealth v1.1."""


def _amount(value, context):
    if value is None or value < 0:
        raise WealthExportError(f"{context}: a nonnegative recorded amount is required")
    return format(value, "f")


def _fact(identifier, updated_at, **content):
    body = {"id": str(identifier), **content}
    version = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**body, "version": version, "updated_at": updated_at.isoformat()}


def _latest_timestamp(*rows):
    return max(row.updated_at for row in rows)


def _observations(prop):
    grouped = defaultdict(list)
    for row in prop.capital.order_by("capital_structure_date", "pk"):
        grouped[row.capital_structure_date].append(row)
    if not grouped:
        raise WealthExportError(f"Property {prop.pk}: capital observations are required")
    value = debt = None
    loan_id = None
    value_source = debt_source = None
    facts = []
    sources = []
    for on, rows in grouped.items():
        for field in ("capital_structure_value", "capital_structure_debt"):
            known = {getattr(row, field) for row in rows if getattr(row, field) is not None}
            if len(known) > 1:
                raise WealthExportError(f"Property {prop.pk}, {on}: conflicting {field} observations")
        debt_rows = [row for row in rows if row.capital_structure_debt is not None]
        if len({row.loan_id for row in debt_rows if row.capital_structure_debt != 0}) > 1:
            raise WealthExportError(f"Property {prop.pk}, {on}: simultaneous loans cannot be represented")
        for row in rows:
            if row.capital_structure_value is not None:
                value = row.capital_structure_value
                value_source = row
            if row.capital_structure_debt is not None:
                debt = row.capital_structure_debt
                loan_id = str(row.loan_id) if debt != 0 and row.loan_id else None
                debt_source = row
        if value is None or debt is None:
            missing = "value" if value is None else "debt"
            raise WealthExportError(f"Property {prop.pk}, {on}: initial {missing} is unknown; no backfill is invented")
        if debt and not loan_id:
            raise WealthExportError(f"Property {prop.pk}, {on}: nonzero debt requires a loan")
        timestamp_rows = [*rows, value_source, debt_source]
        facts.append(_fact(
            f"capital:{prop.pk}:{on.isoformat()}", _latest_timestamp(*timestamp_rows),
            property_id=str(prop.pk), date=on.isoformat(), value=_amount(value, "Capital value"),
            debt_balance=_amount(debt, "Capital debt"), loan_id=loan_id,
        ))
        sources.extend(rows)
    return facts, sources


def build_wealth_export(*, subject, issuer=None, as_of=None):
    """Export all stored history and property-level snapshots at ``as_of``."""
    identities = OIDCIdentity.objects.filter(subject=subject)
    if issuer is not None:
        identities = identities.filter(issuer=issuer)
    identities = list(identities.select_related("user"))
    if len(identities) != 1:
        raise WealthExportError("OIDC subject must identify exactly one user; supply --issuer if ambiguous")
    as_of = as_of or timezone.localdate()
    payload = {
        "source": "rent", "version": "v1.1", "subject_id": subject,
        "generated_at": timezone.now().isoformat(), "properties": [], "loans": [],
        "capital_observations": [], "transactions": [], "arrears": [], "deposits": [],
    }
    properties = Property.objects.filter(owned_by__user_id=identities[0].user_id).order_by("pk")
    for prop in properties:
        if not prop.currency or not re.fullmatch(r"[A-Z]{3}", prop.currency):
            raise WealthExportError(f"Property {prop.pk}: currency must be three uppercase letters")
        observations, capital_rows = _observations(prop)
        payload["capital_observations"].extend(observations)
        loans = list(prop.loans.order_by("pk"))
        loan_ids = {str(loan.pk) for loan in loans}
        for loan in loans:
            if loan.currency != prop.currency or not loan.lender.strip():
                raise WealthExportError(f"Loan {loan.pk}: lender and matching property currency are required")
            payload["loans"].append(_fact(loan.pk, loan.updated_at, property_id=str(prop.pk), lender=loan.lender, currency=loan.currency))
        for observation in observations:
            if observation["loan_id"] is not None and observation["loan_id"] not in loan_ids:
                raise WealthExportError(f"Property {prop.pk}: observation loan belongs to a different property")
        latest = observations[-1]
        lender = next((loan.lender for loan in loans if str(loan.pk) == latest["loan_id"]), None)
        payload["properties"].append(_fact(
            prop.pk, _latest_timestamp(prop, *capital_rows, *loans), name=prop.name,
            currency=prop.currency, value=latest["value"], value_date=latest["date"],
            debt_balance=latest["debt_balance"], lender=lender,
        ))
        transactions = list(prop.transactions.order_by("date", "pk"))
        transaction_ids = {tx.pk for tx in transactions}
        for tx in transactions:
            if tx.currency != prop.currency:
                raise WealthExportError(f"Transaction {tx.pk}: currency must match property currency")
            if tx.category not in dict(TRANSACTION_CATEGORIES):
                raise WealthExportError(f"Transaction {tx.pk}: unsupported category")
            kind = {"loan_interest": "interest", "loan_principal": "principal"}.get(tx.category)
            if kind is None:
                kind = tx.category if tx.category in {"rent", "cost_reimbursement"} else "cost"
            loan = None
            if kind in {"interest", "principal"}:
                loan = str(tx.loan_id) if tx.loan_id else None
                if loan not in loan_ids:
                    raise WealthExportError(f"Transaction {tx.pk}: loan must belong to its property")
            amount = abs(tx.amount) if kind == "cost" else tx.amount
            payload["transactions"].append(_fact(
                f"transaction:{tx.pk}", tx.updated_at, property_id=str(prop.pk), date=tx.date.isoformat(),
                amount=_amount(amount, f"Transaction {tx.pk}"), currency=tx.currency, type=kind, loan_id=loan,
            ))
        tenants = list(prop.tenants.order_by("pk"))
        lease_rows = [row for tenant in tenants for row in tenant.rent_history.all()]
        for row in lease_rows:
            if row.currency != prop.currency:
                raise WealthExportError(f"Property {prop.pk}: lease rent currency must match property currency")
        movements = list(DepositMovement.objects.filter(tenant__property=prop).select_related("transaction").order_by("date", "pk"))
        held = Decimal("0")
        for movement in movements:
            if movement.currency != prop.currency:
                raise WealthExportError(f"Deposit movement {movement.pk}: currency must match property currency")
            if movement.kind not in {"received", "returned", "applied"}:
                raise WealthExportError(f"Deposit movement {movement.pk}: unsupported kind")
            amount = _amount(movement.amount, f"Deposit movement {movement.pk}")
            if movement.kind == "applied":
                linked = movement.transaction
                if (linked is None or linked.pk not in transaction_ids or linked.tenant_id != movement.tenant_id
                        or linked.category != movement.applied_to or linked.date != movement.date
                        or linked.currency != movement.currency or linked.amount < movement.amount):
                    raise WealthExportError(f"Deposit movement {movement.pk}: invalid applied transaction")
            payload["transactions"].append(_fact(
                f"deposit:{movement.pk}", movement.updated_at, property_id=str(prop.pk), date=movement.date.isoformat(),
                amount=amount, currency=movement.currency,
                type="deposit_in" if movement.kind == "received" else "deposit_out", loan_id=None,
            ))
            if movement.date <= as_of:
                held += deposit_signed_amount(movement.kind, movement.amount)
        arrears = sum((max(-tenant.debt(as_of), Decimal("0")) for tenant in tenants), Decimal("0"))
        dependencies = [prop, *tenants, *lease_rows, *transactions, *movements]
        for collection, balance in (("arrears", arrears), ("deposits", held)):
            payload[collection].append(_fact(
                f"{collection}:{prop.pk}:{as_of.isoformat()}", _latest_timestamp(*dependencies),
                property_id=str(prop.pk), as_of=as_of.isoformat(), amount=_amount(balance, collection),
            ))
    return payload
