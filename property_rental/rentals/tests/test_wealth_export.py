"""The Wealth export is a read-only financial boundary, scoped by OIDC identity."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from rentals.models import OIDCIdentity, Property_capital_structure, Transaction
from rentals.tests.factories import (
    LeaseRentFactory, PropertyFactory, TenantFactory, TransactionFactory, UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def source():
    user = UserFactory()
    OIDCIdentity.objects.create(user=user, subject="wealth-sub", issuer="https://auth.example/")
    prop = PropertyFactory(owned_by=user.landlord, name="Investment flat", currency="GBP")
    observation = Property_capital_structure.objects.create(
        property=prop, capital_structure_date=date(2024, 1, 1),
        capital_structure_value=Decimal("150000"), capital_structure_debt=Decimal("0"),
    )
    return user, prop, observation


def export(source, **kwargs):
    from rentals.services.wealth_export import build_wealth_export
    return build_wealth_export(subject="wealth-sub", as_of=date(2024, 3, 15), **kwargs)


def test_export_is_read_only_scoped_and_hashes_content(source, tmp_path):
    _, prop, observation = source
    TransactionFactory(property=prop, date=date(2024, 2, 1), category="utilities", amount=Decimal("-40"), currency="GBP", comment="PRIVATE COMMENT")
    other = PropertyFactory(name="PRIVATE OTHER PROPERTY")
    Property_capital_structure.objects.create(property=other, capital_structure_date=date(2024, 1, 1), capital_structure_value=1, capital_structure_debt=0)
    out = tmp_path / "rent.json"

    def readonly(execute, sql, params, many, context):
        assert sql.lstrip().upper().startswith("SELECT"), sql
        return execute(sql, params, many, context)

    with connection.execute_wrapper(readonly):
        call_command("export_wealth", out=str(out), subject="wealth-sub", as_of="2024-03-15", stdout=StringIO())
        data = export(source)
    written = json.loads(out.read_text())
    assert {k: v for k, v in written.items() if k != "generated_at"} == {k: v for k, v in data.items() if k != "generated_at"}
    assert data["version"] == "v1.1"
    assert data["subject_id"] == "wealth-sub"
    assert [p["id"] for p in data["properties"]] == [str(prop.pk)]
    assert data["transactions"][0]["type"] == "cost"
    assert data["transactions"][0]["amount"] == "40.00"
    assert data["capital_observations"][0]["updated_at"] == observation.updated_at.isoformat()
    assert "PRIVATE" not in json.dumps(data)
    old_version = data["properties"][0]["version"]
    prop.name = "Renamed flat"
    prop.save()
    assert export(source)["properties"][0]["version"] != old_version


def test_subject_must_match_exactly_one_external_identity(source):
    from rentals.services.wealth_export import WealthExportError, build_wealth_export
    with pytest.raises(WealthExportError, match="subject"):
        build_wealth_export(subject="missing")
    second = UserFactory()
    OIDCIdentity.objects.create(user=second, subject="wealth-sub", issuer="https://other.example/")
    with pytest.raises(WealthExportError, match="issuer"):
        export(source)
    assert export(source, issuer="https://auth.example/")["properties"]


def test_partial_observations_carry_forward_without_backfill(source):
    _, prop, _ = source
    Property_capital_structure.objects.create(property=prop, capital_structure_date=date(2024, 2, 1), capital_structure_value=160000)
    data = export(source)
    assert [(o["date"], o["value"], o["debt_balance"]) for o in data["capital_observations"]] == [
        ("2024-01-01", "150000.00", "0.00"), ("2024-02-01", "160000.00", "0.00"),
    ]
    assert data["properties"][0]["value_date"] == "2024-02-01"
    from rentals.services.wealth_export import WealthExportError
    Property_capital_structure.objects.filter(property=prop).update(capital_structure_debt=None)
    with pytest.raises(WealthExportError, match="debt"):
        export(source)


def test_export_rejects_currency_mismatch_and_unsupported_income(source):
    from rentals.services.wealth_export import WealthExportError
    _, prop, _ = source
    tx = TransactionFactory(property=prop, date=date(2024, 2, 1), amount=10, currency="USD")
    with pytest.raises(WealthExportError, match="currency"):
        export(source)
    Transaction.objects.filter(pk=tx.pk).update(currency="GBP", category="unknown")
    with pytest.raises(WealthExportError, match="category"):
        export(source)


def test_command_does_not_replace_output_on_invalid_source(source, tmp_path):
    out = tmp_path / "rent.json"
    out.write_text("previous export")
    with pytest.raises(CommandError):
        call_command("export_wealth", out=str(out), subject="missing", stdout=StringIO())
    assert out.read_text() == "previous export"


def test_loan_history_and_payments_export_with_real_timestamps(source, tmp_path):
    from rentals.models import Loan
    _, prop, _ = source
    loan = Loan.objects.create(property=prop, lender="Bank", currency="GBP", start_date=date(2024, 1, 1), reference="PRIVATE ACCOUNT")
    Property_capital_structure.objects.create(property=prop, capital_structure_date=date(2024, 2, 1), capital_structure_debt=50000, loan=loan)
    Property_capital_structure.objects.create(property=prop, capital_structure_date=date(2024, 3, 1), capital_structure_debt=49500, loan=loan)
    interest = TransactionFactory(property=prop, category="loan_interest", loan=loan, amount=Decimal("100"), currency="GBP", date=date(2024, 3, 1))
    principal = TransactionFactory(property=prop, category="loan_principal", loan=loan, amount=Decimal("500"), currency="GBP", date=date(2024, 3, 1))
    reimbursement = TransactionFactory(property=prop, category="cost_reimbursement", amount=Decimal("30"), currency="GBP", date=date(2024, 3, 1))
    data = export(source)
    (tmp_path / "wealth-v11.json").write_text(json.dumps(data))
    assert len(data["capital_observations"]) == 3
    assert data["properties"][0]["debt_balance"] == "49500.00"
    assert data["loans"][0]["id"] == str(loan.pk)
    assert "PRIVATE" not in json.dumps(data)
    by_id = {tx["id"]: tx for tx in data["transactions"]}
    assert by_id[f"transaction:{interest.pk}"]["type"] == "interest"
    assert by_id[f"transaction:{principal.pk}"]["loan_id"] == str(loan.pk)
    assert by_id[f"transaction:{reimbursement.pk}"]["type"] == "cost_reimbursement"
    assert by_id[f"transaction:{interest.pk}"]["updated_at"] == interest.updated_at.isoformat()
    previous = by_id[f"transaction:{principal.pk}"]["version"]
    Transaction.objects.filter(pk=principal.pk).update(updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert {tx["id"]: tx for tx in export(source)["transactions"]}[f"transaction:{principal.pk}"]["version"] == previous
    Transaction.objects.filter(pk=principal.pk).update(amount=600)
    assert {tx["id"]: tx for tx in export(source)["transactions"]}[f"transaction:{principal.pk}"]["version"] != previous


def test_deposit_application_offsets_cash_and_retains_income_once(source):
    from rentals.services.deposits import create_movement
    _, prop, _ = source
    tenant = TenantFactory(property=prop, first_name="PRIVATE TENANT", lease_start=date(2024, 1, 1), payday=1)
    LeaseRentFactory(tenant=tenant, date_rent_set=date(2024, 1, 1), rent=1000, currency="GBP")
    received = create_movement(tenant, date=date(2024, 1, 1), kind="received", currency="GBP", amount=Decimal("1500"))
    applied = create_movement(tenant, date=date(2024, 1, 10), kind="applied", currency="GBP", amount=Decimal("400"), applied_to="rent")
    TransactionFactory(property=prop, tenant=tenant, date=date(2024, 1, 10), category="rent", currency="GBP", amount=600)
    returned = create_movement(tenant, date=date(2024, 2, 1), kind="returned", currency="GBP", amount=Decimal("100"))
    data = export(source)
    assert data["deposits"][0]["amount"] == "1000.00"
    assert data["arrears"][0]["amount"] == "2000.00"
    assert sum(Decimal(tx["amount"]) for tx in data["transactions"] if tx["type"] == "rent") == 1000
    assert [(tx["type"], tx["amount"]) for tx in data["transactions"] if tx["id"].startswith("deposit:")] == [
        ("deposit_in", "1500.00"), ("deposit_out", "400.00"), ("deposit_out", "100.00"),
    ]
    assert "PRIVATE TENANT" not in json.dumps(data)
    # Moving money from the deposit to rent must not create an extra bank receipt.
    on_application = [tx for tx in data["transactions"] if tx["date"] == "2024-01-10"]
    assert sum(Decimal(tx["amount"]) * (-1 if tx["type"] == "deposit_out" else 1) for tx in on_application) == 600


def test_conflicting_same_date_observations_are_rejected(source):
    from rentals.services.wealth_export import WealthExportError
    _, prop, _ = source
    Property_capital_structure.objects.create(property=prop, capital_structure_date=date(2024, 1, 1), capital_structure_value=160000)
    with pytest.raises(WealthExportError, match="conflicting"):
        export(source)


def test_same_date_complementary_observations_become_one_snapshot(source):
    _, prop, observation = source
    Property_capital_structure.objects.filter(pk=observation.pk).update(capital_structure_debt=None)
    Property_capital_structure.objects.create(property=prop, capital_structure_date=date(2024, 1, 1), capital_structure_debt=0)
    data = export(source)
    assert len(data["capital_observations"]) == 1
    assert data["capital_observations"][0]["value"] == "150000.00"
    assert data["capital_observations"][0]["debt_balance"] == "0.00"


def test_invalid_property_currency_is_rejected_before_writing(source):
    from rentals.models import Property
    from rentals.services.wealth_export import WealthExportError
    _, prop, _ = source
    Property.objects.filter(pk=prop.pk).update(currency="gbp")
    with pytest.raises(WealthExportError, match="currency"):
        export(source)
