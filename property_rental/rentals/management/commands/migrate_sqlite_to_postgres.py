"""One-shot migration: SQLite (``db.sqlite3``) -> Postgres.

Runnable as a Django management command::

    # Dev/local convenience (writes back to SQLite — only useful for a
    # dry-run against a throwaway DB):
    python manage.py migrate_sqlite_to_postgres

    # Real run: point ``DJANGO_SETTINGS_MODULE`` at the prod settings so
    # ``default`` is the Postgres connection, and supply the SQLite source
    # path explicitly (the source DB may live outside ``BASE_DIR`` in prod):
    DJANGO_SETTINGS_MODULE=property_rental.settings.prod \
        python manage.py migrate_sqlite_to_postgres \
            --sqlite-path /srv/app/db.sqlite3

What it does, per model in ``MODELS`` (the 8 ``rentals`` tables):

1. Reads every row from the SQLite source DB through a **raw** ``sqlite3``
   connection (never Django's ``default`` connection) so the source is
   read-only regardless of what ``DATABASES['default']` is wired to.
2. Bulk-inserts to Django's ``default`` connection in batches of 500.
3. Counts rows on the destination and raises ``SystemExit`` on mismatch.

The script is *idempotent-ish*: if a destination table already has rows
matching the source count, it is skipped (so a re-run after a partial
success doesn't double-insert). It is **not** safe to run twice against a
destination that was only partially populated — fix that case manually.

The verification logic lives in :func:`verify_counts` and is unit-tested
without a live Postgres connection.
"""

from __future__ import annotations

import sqlite3

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

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

#: All rentals models in dependency-safe order (parents before FK children).
#: ``User`` must come before ``Landlord``/``Tenant`` (FK back to User),
#: ``Landlord`` before ``Property``, ``Property`` before its capital /
#: tenant / transaction children, ``Tenant`` before ``Lease_rent``.
MODELS = [
    User,
    Landlord,
    Property,
    Property_capital_structure,
    Tenant,
    Lease_rent,
    Transaction,
    FX,
]

#: Bulk-insert chunk size. 500 balances memory and round-trip count for
#: tables that are expected to remain small-to-moderate in this app.
BATCH_SIZE = 500


class Command(BaseCommand):
    """``python manage.py migrate_sqlite_to_postgres``."""

    help = "Copy all rows from db.sqlite3 into the default (Postgres) DB, verifying row counts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="Path to the source SQLite DB (default: <BASE_DIR>/db.sqlite3).",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            default=False,
            help="Do not run `migrate` against the destination first "
            "(useful when the destination is already at the latest schema).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Read SQLite counts only; do not insert anything. "
            "Useful for sanity-checking the source DB before a real run.",
        )

    def handle(self, *args, **options):
        sqlite_path = options["sqlite_path"]
        skip_migrate = options["skip_migrate"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no inserts will be performed."))
            for model in MODELS:
                cols, rows = read_sqlite_rows(sqlite_path, model)
                self.stdout.write(f"  {model.__name__}: sqlite={len(rows)} rows")
            return

        if not skip_migrate:
            # Bring the (assumed empty) destination DB up to the current
            # schema before inserting. The brief explicitly asks for this.
            self.stdout.write("Applying migrations to destination DB ...")
            call_command("migrate", verbosity=1)

        summary = {}
        for model in MODELS:
            cols, rows = read_sqlite_rows(sqlite_path, model)
            before = len(rows)

            existing = model.objects.using("default").count()
            if existing == before and before > 0:
                # Idempotency short-circuit: the table already matches the
                # source. Skip the bulk insert to avoid UNIQUE violations.
                self.stdout.write(
                    self.style.WARNING(
                        f"  {model.__name__}: destination already has {existing} rows "
                        f"(== source); skipping insert."
                    )
                )
                summary[model.__name__] = (before, existing)
                continue

            if existing > 0 and existing != before:
                # Partial prior run. Bail loudly rather than silently
                # double-insert; the operator should clean up manually.
                raise CommandError(
                    f"ABORT {model.__name__}: destination has {existing} rows but "
                    f"source has {before}. Partial prior migration? "
                    f"Truncate the destination table and re-run."
                )

            # Build model instances from the raw rows. ``read_sqlite_rows``
            # already returns dicts keyed only by the current model's Python
            # attribute names, so no extra filtering is needed here.
            objs = [model(**r) for r in rows]
            for i in range(0, len(objs), BATCH_SIZE):
                model.objects.using("default").bulk_create(
                    objs[i : i + BATCH_SIZE], batch_size=BATCH_SIZE
                )

            after = model.objects.using("default").count()
            summary[model.__name__] = (before, after)

        verify_counts(summary, abort=CommandError)

        self.stdout.write(self.style.SUCCESS("Migration OK. Row counts:"))
        for name, (b, a) in summary.items():
            self.stdout.write(f"  {name}: {b} -> {a}")


# ---------------------------------------------------------------------------
# Pure helpers (kept module-level so unit tests can import them directly
# without spinning up Django's app registry for the comparison logic).
# ---------------------------------------------------------------------------


def read_sqlite_rows(sqlite_path, model):
    """Read every row of ``model``'s table from the SQLite DB at ``sqlite_path``.

    Uses a raw ``sqlite3`` connection so the read is independent of
    Django's ``DATABASES['default']`` (which is the Postgres destination
    during a real migration run). Returns ``(field_names, list_of_dicts)``
    where each dict is keyed by the model's **Python attribute** name
    (e.g. ``user`` for an FK), so callers can do ``model(**row)`` directly.

    NB: Django stores FK columns as ``<field_name>_id`` in the DB. We
    therefore SELECT using ``field.column`` (the real DB column name) but
    remap back to ``field.name`` (the Python attribute) so the resulting
    dicts can be passed straight to ``model(**kwargs)``. Using only
    ``field.name`` here would crash on every FK column ("no such column:
    user").
    """
    table = model._meta.db_table
    fields = model._meta.fields
    db_cols = [f.column for f in fields]  # actual DB column names
    py_names = [f.name for f in fields]  # Python attribute names
    col_to_attr = dict(zip(db_cols, py_names))

    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.row_factory = sqlite3.Row
        # Column names are controlled by us (Django field.column), not
        # user input, so the f-string interpolation here is safe.
        rows = conn.execute(
            f"SELECT {', '.join(db_cols)} FROM {table}"
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = {col_to_attr[k]: v for k, v in dict(r).items()}
        out.append(d)
    return py_names, out


def verify_counts(summary, abort=None, logger=None):
    """Verify that every ``(before, after)`` pair in ``summary`` matches.

    ``summary`` is ``{model_name: (sqlite_count, postgres_count)}``.

    On mismatch, raise ``abort(...)`` (defaults to ``SystemExit``) with a
    descriptive message. ``logger``, if given, is called once per row with
    a human-readable line. Returns ``True`` on success.

    Kept as a standalone function so it can be unit-tested with mock
    summary dicts — no DB connection required.
    """
    abort = abort or SystemExit
    ok = True
    for name, (before, after) in summary.items():
        if before != after:
            ok = False
            msg = f"MISMATCH {name}: sqlite={before} postgres={after}"
            if logger is not None:
                logger.write(msg)
            raise abort(
                f"MISMATCH {name}: sqlite={before} postgres={after}"
            )
        if logger is not None:
            logger.write(f"  {name}: {before} -> {after}")
    return ok


def iter_batches(seq, size):
    """Yield successive ``size``-chunks from ``seq``. Pure helper for tests."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
