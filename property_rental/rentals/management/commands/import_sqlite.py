"""One-shot, auditable import of legacy application rows from SQLite."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from rentals.models import (
    FX, Landlord, Lease_rent, Property, Property_capital_structure, Tenant,
    Transaction, User,
)


MODELS = [
    User, Landlord, Property, Property_capital_structure, Tenant, Lease_rent,
    Transaction, FX,
]


def read_source(source: Path):
    uri = f"file:{source.resolve().as_posix()}?mode=ro"
    try:
        db = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise CommandError(f"Cannot open SQLite source read-only: {exc}") from exc
    db.row_factory = sqlite3.Row
    result = {}
    try:
        for model in MODELS:
            table = model._meta.db_table
            expected = [field.column for field in model._meta.concrete_fields]
            actual = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
            missing = sorted(set(expected) - set(actual))
            if missing:
                raise CommandError(f"Unsupported source schema for {table}; missing columns: {missing}")
            selected = ", ".join(f'"{column}"' for column in expected)
            result[model] = [dict(row) for row in db.execute(
                f'SELECT {selected} FROM "{table}" ORDER BY "{model._meta.pk.column}"'
            )]
    except sqlite3.Error as exc:
        raise CommandError(f"Invalid SQLite source: {exc}") from exc
    finally:
        db.close()
    return result


def relationship_errors(rows_by_model):
    errors = {model: [] for model in MODELS}
    source_ids = {
        model: {row[model._meta.pk.column] for row in rows}
        for model, rows in rows_by_model.items()
    }
    for model, rows in rows_by_model.items():
        for field in model._meta.concrete_fields:
            if not field.is_relation or field.remote_field.model not in source_ids:
                continue
            for row in rows:
                value = row[field.column]
                if value is not None and value not in source_ids[field.remote_field.model]:
                    errors[model].append(
                        f"{model._meta.db_table}.{field.column}={value} has no source parent"
                    )
    return errors


def source_value(field, value):
    value = field.to_python(value)
    if value is not None and field.get_internal_type() == "DecimalField":
        value = value.quantize(Decimal(1).scaleb(-field.decimal_places))
    if value is not None and field.get_internal_type() == "DateTimeField":
        if timezone.is_naive(value) and timezone.is_aware(timezone.now()):
            value = timezone.make_aware(value)
    return value


def destination_exactly_matches(rows_by_model):
    for model, source_rows in rows_by_model.items():
        fields = list(model._meta.concrete_fields)
        destination = list(model.objects.order_by(model._meta.pk.name).values_list(
            *(field.attname for field in fields)
        ))
        if len(destination) != len(source_rows):
            return False
        for source, dest_values in zip(source_rows, destination):
            for field, dest in zip(fields, dest_values):
                if model is User and field.name == "password":
                    if dest and not str(dest).startswith("!"):
                        return False
                    continue
                expected = source_value(field, source[field.column])
                if expected != dest:
                    return False
    return True


def build_report(rows_by_model, status, sequence_status, errors=None):
    errors = errors or {model: [] for model in MODELS}
    return {
        "status": status,
        "models": {
            model.__name__: {
                "source_count": len(rows_by_model[model]),
                "destination_count": model.objects.count(),
                "relationship_errors": errors[model],
                "sequence_status": sequence_status,
            }
            for model in MODELS
        },
    }


def reset_sequences():
    sql = connection.ops.sequence_reset_sql(no_style(), MODELS)
    with connection.cursor() as cursor:
        for statement in sql:
            cursor.execute(statement)
    return "reset" if sql else "not-required"


def lock_business_tables():
    if connection.vendor != "postgresql":
        return
    tables = ", ".join(
        connection.ops.quote_name(model._meta.db_table) for model in MODELS
    )
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {tables} IN EXCLUSIVE MODE")


class Command(BaseCommand):
    help = "Import legacy application rows from a read-only SQLite database."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--report")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        source = Path(options["source"])
        if not source.is_file():
            raise CommandError(f"SQLite source does not exist: {source}")
        rows = read_source(source)
        errors = relationship_errors(rows)
        if any(errors.values()):
            report = build_report(rows, "failed", "not-run", errors)
            self._write_report(report, options["report"], stdout=False)
            raise CommandError("Source relationship validation failed: " + json.dumps(
                {model.__name__: value for model, value in errors.items() if value}, sort_keys=True
            ))

        if options["dry_run"]:
            report = build_report(rows, "dry-run", "not-run", errors)
            self._write_report(report, options["report"])
            return

        with transaction.atomic():
            lock_business_tables()
            counts = {model: model.objects.count() for model in MODELS}
            if any(counts.values()):
                if destination_exactly_matches(rows):
                    sequence_status = reset_sequences()
                    status = "reconciled"
                else:
                    occupied = ", ".join(
                        f"{model.__name__}={count}"
                        for model, count in counts.items() if count
                    )
                    raise CommandError(
                        f"Destination business tables must be empty ({occupied})"
                    )
            else:
                status = "imported"
                for model in MODELS:
                    objects = []
                    for row in rows[model]:
                        values = {
                            field.attname: source_value(field, row[field.column])
                            for field in model._meta.concrete_fields
                        }
                        obj = model(**values)
                        if model is User:
                            obj.set_unusable_password()
                        objects.append(obj)
                    model.objects.bulk_create(objects, batch_size=500)

                if not destination_exactly_matches(rows):
                    raise CommandError("Imported rows failed count or value reconciliation")
                sequence_status = reset_sequences()

        report = build_report(rows, status, sequence_status, errors)
        self._write_report(report, options["report"])

    def _write_report(self, report, path, stdout=True):
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if path:
            Path(path).write_text(serialized, encoding="utf-8")
        if stdout:
            self.stdout.write(serialized.rstrip())
