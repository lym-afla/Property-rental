import json
import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from rentals.models import FX, Landlord, Property, User


BUSINESS_MODELS = [User, Landlord, Property, FX]


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
    source = sqlite3.connect(path)
    connection.connection.backup(source)
    source.close()
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
        "relationship_errors": [], "sequence_status": "reset",
    }


@pytest.mark.django_db(transaction=True)
def test_exact_rerun_is_reconciled_without_inserting(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    call_command("import_sqlite", source=str(source))
    call_command("import_sqlite", source=str(source))
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
def test_dry_run_writes_deterministic_report_without_destination_writes(tmp_path):
    source, _ = _source_snapshot(tmp_path)
    report_path = tmp_path / "report.json"
    call_command("import_sqlite", source=str(source), report=str(report_path), dry_run=True)
    assert User.objects.count() == 0
    report = json.loads(report_path.read_text())
    assert report["status"] == "dry-run"
    assert report["models"]["FX"]["source_count"] == 1
    assert report["models"]["FX"]["destination_count"] == 0
