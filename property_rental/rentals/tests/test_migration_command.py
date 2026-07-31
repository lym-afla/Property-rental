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
from rentals.models import FX, Landlord, Property, User


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
    assert report["models"]["Property"] == {
        "source_count": 1, "destination_count": 1,
        "relationship_errors": [], "sequence_status": "not-required",
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


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL integration coverage")
@pytest.mark.django_db(transaction=True)
def test_postgresql_sequence_allows_next_generated_id_after_explicit_import(tmp_path):
    source, ids = _source_snapshot(tmp_path)
    call_command("import_sqlite", source=str(source))
    created = User.objects.create_user("after-import")
    assert created.pk > ids["user"]
