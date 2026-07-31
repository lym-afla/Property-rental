import json
import sqlite3
from datetime import date
from decimal import Decimal
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from rentals.management.commands.import_sqlite import MODELS
from rentals.models import (
    FX,
    Landlord,
    Lease_rent,
    Property,
    Property_capital_structure,
    Tenant,
    Transaction,
    User,
)


BUSINESS_MODELS = [User, Landlord, Property, FX]


def _sqlite_value(value):
    if isinstance(value, (date, Decimal)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat(sep=" ")
    if isinstance(value, bool):
        return int(value)
    return value


def _write_source_sqlite(path):
    """Serialize application rows without depending on the destination backend."""
    source = sqlite3.connect(path)
    try:
        for model in MODELS:
            fields = list(model._meta.concrete_fields)
            definitions = []
            for field in fields:
                if field.primary_key:
                    sql_type = "INTEGER PRIMARY KEY"
                elif field.get_internal_type() in {
                    "AutoField", "BigAutoField", "IntegerField", "PositiveIntegerField",
                    "BooleanField", "ForeignKey", "OneToOneField",
                }:
                    sql_type = "INTEGER"
                else:
                    sql_type = "TEXT"
                definitions.append(f'"{field.column}" {sql_type}')
            source.execute(
                f'CREATE TABLE "{model._meta.db_table}" ({", ".join(definitions)})'
            )
            rows = model.objects.order_by(model._meta.pk.name).values_list(
                *(field.attname for field in fields)
            )
            placeholders = ", ".join("?" for _ in fields)
            columns = ", ".join(f'"{field.column}"' for field in fields)
            source.executemany(
                f'INSERT INTO "{model._meta.db_table}" ({columns}) VALUES ({placeholders})',
                [tuple(_sqlite_value(value) for value in row) for row in rows],
            )
        # Prove system-table contents are irrelevant to application emptiness.
        source.execute(
            "CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT, applied TEXT)"
        )
        source.execute(
            "INSERT INTO django_migrations VALUES (1, 'rentals', 'fixture', '2026-01-01')"
        )
        source.commit()
    finally:
        source.close()


def _source_snapshot(tmp_path):
    user = User.objects.create_user(
        username="legacy-owner", password="legacy-secret", is_landlord=True
    )
    landlord = user.landlord
    prop = Property.objects.create(
        id=41, owned_by=landlord, name="Home", location="Moscow", num_bedrooms=2
    )
    FX.objects.create(
        id=73, date=date(2026, 1, 1), from_currency="USD", to_currency="EUR",
        rate=Decimal("0.9000000000"),
    )
    path = tmp_path / "legacy.sqlite3"
    _write_source_sqlite(path)
    Property.objects.all().delete()
    FX.objects.all().delete()
    User.objects.all().delete()
    return path, {"user": user.pk, "landlord": landlord.pk, "property": prop.pk}


def _clear_destination_rows():
    for model in reversed(MODELS):
        model.objects.all().delete()


def _multi_user_source_snapshot(tmp_path, *, selected_tenant_user=None):
    selected = User.objects.create_user(
        id=101,
        username="Yaroslav",
        password="legacy-secret",
        is_landlord=True,
    )
    excluded = User.objects.create_user(
        id=202,
        username="Other",
        password="other-secret",
        is_landlord=True,
    )

    selected_property = Property.objects.create(
        id=401,
        owned_by=selected.landlord,
        name="Selected home",
        location="Moscow",
        num_bedrooms=2,
    )
    excluded_property = Property.objects.create(
        id=402,
        owned_by=excluded.landlord,
        name="Excluded home",
        location="Berlin",
        num_bedrooms=1,
    )
    Property_capital_structure.objects.create(
        id=501,
        property=selected_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("100000.00"),
    )
    Property_capital_structure.objects.create(
        id=502,
        property=excluded_property,
        capital_structure_date=date(2026, 1, 1),
        capital_structure_value=Decimal("200000.00"),
    )

    selected_tenant = Tenant.objects.create(
        id=601,
        user=selected_tenant_user,
        property=selected_property,
        first_name="Selected",
        last_name="Tenant",
        phone="555-0101",
        lease_start=date(2026, 1, 10),
    )
    excluded_tenant = Tenant.objects.create(
        id=602,
        user=None,
        property=excluded_property,
        first_name="Excluded",
        last_name="Tenant",
        phone="555-0202",
        lease_start=date(2026, 2, 10),
    )
    Lease_rent.objects.create(
        id=701,
        tenant=selected_tenant,
        date_rent_set=date(2026, 1, 10),
        rent=Decimal("1200.00"),
    )
    Lease_rent.objects.create(
        id=702,
        tenant=excluded_tenant,
        date_rent_set=date(2026, 2, 10),
        rent=Decimal("900.00"),
    )
    Transaction.objects.create(
        id=801,
        property=selected_property,
        tenant=selected_tenant,
        date=date(2026, 1, 15),
        amount=Decimal("1200.00"),
        category="rent",
    )
    Transaction.objects.create(
        id=802,
        property=excluded_property,
        tenant=excluded_tenant,
        date=date(2026, 2, 15),
        amount=Decimal("900.00"),
        category="rent",
    )
    FX.objects.create(
        id=901,
        date=date(2026, 1, 1),
        from_currency="USD",
        to_currency="EUR",
        rate=Decimal("0.9000000000"),
    )
    FX.objects.create(
        id=902,
        date=date(2026, 1, 1),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.1000000000"),
    )

    path = tmp_path / "multi-user.sqlite3"
    _write_source_sqlite(path)
    _clear_destination_rows()
    return path, {
        "selected_user": selected.pk,
        "excluded_user": excluded.pk,
        "selected_landlord": selected.landlord.pk,
        "excluded_landlord": excluded.landlord.pk,
        "selected_property": selected_property.pk,
        "excluded_property": excluded_property.pk,
        "selected_tenant": selected_tenant.pk,
        "excluded_tenant": excluded_tenant.pk,
        "selected_transaction": 801,
        "excluded_transaction": 802,
    }


@pytest.mark.django_db(transaction=True)
def test_import_ignores_system_rows_preserves_keys_relationships_and_disables_password(tmp_path):
    source, ids = _source_snapshot(tmp_path)
    report_path = tmp_path / "report.json"

    call_command("import_sqlite", source=str(source), report=str(report_path))

    user = User.objects.get(pk=ids["user"])
    assert not user.has_usable_password()
    assert user.landlord.pk == ids["landlord"]
    assert Property.objects.get(pk=ids["property"]).owned_by_id == ids["landlord"]
    report = json.loads(report_path.read_text())
    assert report["status"] == "imported"
    expected_sequence_status = (
        "reset" if connection.vendor == "postgresql" else "not-required"
    )
    assert report["models"]["Property"] == {
        "source_count": 1, "included_count": 1, "excluded_count": 0,
        "destination_count": 1,
        "relationship_errors": [], "sequence_status": expected_sequence_status,
    }


@pytest.mark.django_db(transaction=True)
def test_exact_rerun_is_reconciled_without_inserting(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    call_command("import_sqlite", source=str(source))
    with mock.patch.object(
        connection.ops, "sequence_reset_sql",
        wraps=connection.ops.sequence_reset_sql,
    ) as sequence_reset:
        call_command("import_sqlite", source=str(source))
    sequence_reset.assert_called_once()
    assert User.objects.filter(username="legacy-owner").count() == 1


@pytest.mark.django_db(transaction=True)
def test_partial_or_conflicting_destination_fails(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    User.objects.create_user("unrelated")
    with pytest.raises(CommandError, match="business tables must be empty"):
        call_command("import_sqlite", source=str(source))


@pytest.mark.django_db(transaction=True)
def test_relationship_failure_is_atomic(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    db = sqlite3.connect(source)
    db.execute("UPDATE rentals_property SET owned_by_id = 999999")
    db.commit()
    db.close()
    with pytest.raises(CommandError, match="relationship"):
        call_command("import_sqlite", source=str(source))
    assert User.objects.count() == 0
    assert Property.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_relationship_failure_writes_reconciliation_report(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    db = sqlite3.connect(source)
    db.execute("UPDATE rentals_property SET owned_by_id = 999999")
    db.commit()
    db.close()
    report_path = tmp_path / "failure.json"
    with pytest.raises(CommandError):
        call_command("import_sqlite", source=str(source), report=str(report_path))
    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert report["models"]["Property"]["relationship_errors"] == [
        "rentals_property.owned_by_id=999999 has no source parent"
    ]


@pytest.mark.django_db(transaction=True)
def test_mid_import_exception_rolls_back_every_business_table(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    with mock.patch.object(FX.objects, "bulk_create", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            call_command("import_sqlite", source=str(source))
    assert all(model.objects.count() == 0 for model in BUSINESS_MODELS)


@pytest.mark.django_db(transaction=True)
def test_dry_run_writes_deterministic_report_without_destination_writes(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    report_path = tmp_path / "report.json"
    call_command("import_sqlite", source=str(source), report=str(report_path), dry_run=True)
    assert User.objects.count() == 0
    report = json.loads(report_path.read_text())
    assert report["status"] == "dry-run"
    assert report["models"]["FX"]["source_count"] == 1
    assert report["models"]["FX"]["destination_count"] == 0


@pytest.mark.django_db(transaction=True)
def test_selective_dry_run_reports_included_and_excluded_counts_without_writes(tmp_path):
    source, _ = _multi_user_source_snapshot(tmp_path)
    original_source = source.read_bytes()
    report_path = tmp_path / "dry-run.json"

    call_command(
        "import_sqlite",
        source=str(source),
        include_username="Yaroslav",
        report=str(report_path),
        dry_run=True,
    )

    assert source.read_bytes() == original_source
    assert all(model.objects.count() == 0 for model in MODELS)
    report = json.loads(report_path.read_text())
    assert report["status"] == "dry-run"
    assert report["selection"] == {"include_username": "Yaroslav"}
    assert report["models"]["User"] == {
        "source_count": 2,
        "included_count": 1,
        "excluded_count": 1,
        "destination_count": 0,
        "relationship_errors": [],
        "sequence_status": "not-run",
    }
    assert report["models"]["Landlord"]["included_count"] == 1
    assert report["models"]["Property"]["included_count"] == 1
    assert report["models"]["Tenant"]["included_count"] == 1
    assert report["models"]["Lease_rent"]["included_count"] == 1
    assert report["models"]["Transaction"]["included_count"] == 1
    assert report["models"]["FX"] == {
        "source_count": 2,
        "included_count": 2,
        "excluded_count": 0,
        "destination_count": 0,
        "relationship_errors": [],
        "sequence_status": "not-run",
    }


@pytest.mark.django_db(transaction=True)
def test_selective_import_preserves_selected_user_graph_and_disables_password(tmp_path):
    source, ids = _multi_user_source_snapshot(tmp_path)
    original_source = source.read_bytes()
    dry_report_path = tmp_path / "dry-run.json"
    import_report_path = tmp_path / "import.json"

    call_command(
        "import_sqlite",
        source=str(source),
        include_username="Yaroslav",
        report=str(dry_report_path),
        dry_run=True,
    )
    call_command(
        "import_sqlite",
        source=str(source),
        include_username="Yaroslav",
        report=str(import_report_path),
    )

    assert source.read_bytes() == original_source
    imported = User.objects.get(pk=ids["selected_user"])
    assert imported.username == "Yaroslav"
    assert not imported.has_usable_password()
    assert not User.objects.filter(pk=ids["excluded_user"]).exists()
    assert Landlord.objects.get(pk=ids["selected_landlord"]).user_id == imported.pk
    assert not Landlord.objects.filter(pk=ids["excluded_landlord"]).exists()
    assert Property.objects.get(pk=ids["selected_property"]).owned_by_id == ids["selected_landlord"]
    assert not Property.objects.filter(pk=ids["excluded_property"]).exists()
    assert Tenant.objects.get(pk=ids["selected_tenant"]).property_id == ids["selected_property"]
    assert not Tenant.objects.filter(pk=ids["excluded_tenant"]).exists()
    assert Transaction.objects.get(pk=ids["selected_transaction"]).tenant_id == ids["selected_tenant"]
    assert not Transaction.objects.filter(pk=ids["excluded_transaction"]).exists()

    dry_report = json.loads(dry_report_path.read_text())
    import_report = json.loads(import_report_path.read_text())
    assert dry_report["selection"] == import_report["selection"]
    for model in MODELS:
        model_report = import_report["models"][model.__name__]
        assert (
            dry_report["models"][model.__name__]["included_count"],
            dry_report["models"][model.__name__]["excluded_count"],
        ) == (model_report["included_count"], model_report["excluded_count"])


@pytest.mark.django_db(transaction=True)
def test_selective_import_requires_exactly_one_matching_source_username(tmp_path):
    source, _ = _multi_user_source_snapshot(tmp_path)
    missing_report_path = tmp_path / "missing.json"

    with pytest.raises(CommandError, match="matched 0 source users"):
        call_command(
            "import_sqlite",
            source=str(source),
            include_username="Missing",
            report=str(missing_report_path),
        )
    missing_report = json.loads(missing_report_path.read_text())
    assert missing_report["selection"] == {"include_username": "Missing"}
    assert missing_report["models"]["User"]["relationship_errors"] == [
        "include_username='Missing' matched 0 source users"
    ]

    table = User._meta.db_table
    with sqlite3.connect(source) as db:
        db.execute(f'UPDATE "{table}" SET username = ? WHERE username = ?', ("Yaroslav", "Other"))
        db.commit()

    duplicate_report_path = tmp_path / "duplicate.json"
    with pytest.raises(CommandError, match="matched 2 source users"):
        call_command(
            "import_sqlite",
            source=str(source),
            include_username="Yaroslav",
            report=str(duplicate_report_path),
        )
    duplicate_report = json.loads(duplicate_report_path.read_text())
    assert duplicate_report["selection"] == {"include_username": "Yaroslav"}
    assert duplicate_report["models"]["User"]["relationship_errors"] == [
        "include_username='Yaroslav' matched 2 source users"
    ]
    assert all(model.objects.count() == 0 for model in MODELS)


@pytest.mark.django_db(transaction=True)
def test_selective_import_fails_if_included_record_references_excluded_user(tmp_path):
    excluded_tenant_user = User.objects.create_user(
        id=303,
        username="TenantAccount",
        password="tenant-secret",
        is_landlord=False,
    )
    source, _ = _multi_user_source_snapshot(tmp_path, selected_tenant_user=excluded_tenant_user)
    report_path = tmp_path / "excluded-reference.json"

    with pytest.raises(CommandError, match="excluded user"):
        call_command(
            "import_sqlite",
            source=str(source),
            include_username="Yaroslav",
            report=str(report_path),
        )

    report = json.loads(report_path.read_text())
    assert report["status"] == "failed"
    assert report["selection"] == {"include_username": "Yaroslav"}
    assert report["models"]["Tenant"]["relationship_errors"] == [
        "rentals_tenant.user_id=303 references excluded user"
    ]
    assert all(model.objects.count() == 0 for model in MODELS)


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL integration coverage")
@pytest.mark.django_db(transaction=True)
def test_postgresql_sequence_allows_next_generated_id_after_explicit_import(tmp_path):
    source, ids = _source_snapshot(tmp_path)
    call_command("import_sqlite", source=str(source))
    created = User.objects.create_user("after-import")
    assert created.pk > ids["user"]
