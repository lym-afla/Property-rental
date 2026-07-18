"""Tests for the SQLite -> Postgres migration script (Task 15).

These tests are written so they DON'T need a live Postgres. They cover:

* :func:`verify_counts` — the row-count verification helper — with both
  matching and mismatching summary dicts. This is the heart of the
  "verified per-table row counts" contract.
* :func:`read_sqlite_rows` — reading from the SQLite source through the
  raw ``sqlite3`` connection. This is exercised against a temp file so it
  does not depend on the project's ``db.sqlite3`` existing or being
  populated.
* :func:`iter_batches` — the batching helper.
* The ``Command`` class shape — sanity-check that the management command
  imports, has the expected arguments, and that ``handle`` short-circuits
  with ``--dry-run``.
* A full dry-run-via-``call_command`` smoke test against the live
  ``db.sqlite3`` (if present): the dry-run path must not write anything,
  so this is safe to run regardless of what ``DATABASES['default']`` is.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from rentals.management.commands.migrate_sqlite_to_postgres import (
    BATCH_SIZE,
    Command,
    MODELS,
    iter_batches,
    read_sqlite_rows,
    verify_counts,
)
from rentals.models import FX


# ---------------------------------------------------------------------------
# verify_counts — the per-table verification contract.
# ---------------------------------------------------------------------------


class TestVerifyCounts:
    def test_matching_counts_return_true(self):
        summary = {"User": (5, 5), "FX": (10, 10)}
        assert verify_counts(summary) is True

    def test_matching_counts_with_logger(self):
        # A simple list-as-logger so we can assert the printed lines.
        logged = []

        class _Logger:
            def write(self, msg):
                logged.append(msg)

        summary = {"User": (5, 5)}
        verify_counts(summary, logger=_Logger())
        assert logged == ["  User: 5 -> 5"]

    def test_mismatch_raises_systemexit_by_default(self):
        summary = {"User": (5, 4)}  # source 5, dest 4 — mismatch
        with pytest.raises(SystemExit) as exc:
            verify_counts(summary)
        assert "MISMATCH User" in str(exc.value)
        assert "sqlite=5" in str(exc.value)
        assert "postgres=4" in str(exc.value)

    def test_mismatch_raises_custom_abort(self):
        # The management command passes ``abort=CommandError``.
        summary = {"FX": (3, 7)}
        with pytest.raises(CommandError) as exc:
            verify_counts(summary, abort=CommandError)
        assert "MISMATCH FX" in str(exc.value)

    def test_first_mismatch_aborts_immediately(self):
        # Even if a later table would match, the first mismatch aborts.
        summary = {"User": (1, 2), "FX": (5, 5)}
        with pytest.raises(SystemExit):
            verify_counts(summary)

    def test_empty_summary_is_vacuously_true(self):
        assert verify_counts({}) is True


# ---------------------------------------------------------------------------
# iter_batches — the chunking helper.
# ---------------------------------------------------------------------------


class TestIterBatches:
    def test_full_batches(self):
        seq = list(range(10))
        batches = list(iter_batches(seq, 3))
        assert batches == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

    def test_empty(self):
        assert list(iter_batches([], 500)) == []

    def test_batch_size_constant(self):
        # The contract the migration script depends on.
        assert BATCH_SIZE == 500


# ---------------------------------------------------------------------------
# read_sqlite_rows — reading the source. Uses a temp SQLite file so it
# does NOT depend on the project's db.sqlite3 being populated.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestReadSqliteRows:
    def test_reads_rows_from_source_db(self, tmp_path):
        # Build a tiny SQLite DB with an FX-shaped table.
        sqlite_path = tmp_path / "src.sqlite3"
        conn = sqlite3.connect(str(sqlite_path))
        conn.executescript(
            """
            CREATE TABLE rentals_fx (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                rate NUMERIC NOT NULL
            );
            INSERT INTO rentals_fx (id, date, from_currency, to_currency, rate)
            VALUES
                (1, '2024-01-01', 'EUR', 'USD', 1.10),
                (2, '2024-01-02', 'GBP', 'USD', 1.27);
            """
        )
        conn.commit()
        conn.close()

        cols, rows = read_sqlite_rows(sqlite_path, FX)
        assert cols == ["id", "date", "from_currency", "to_currency", "rate"]
        assert len(rows) == 2
        assert rows[0]["from_currency"] == "EUR"
        assert rows[1]["to_currency"] == "USD"

    def test_missing_table_raises(self, tmp_path):
        # Source DB exists but the table is absent — should surface the
        # sqlite3.OperationalError, not silently return [].
        sqlite_path = tmp_path / "empty.sqlite3"
        sqlite3.connect(str(sqlite_path)).close()
        with pytest.raises(sqlite3.OperationalError):
            read_sqlite_rows(sqlite_path, FX)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(sqlite3.Error):
            read_sqlite_rows(tmp_path / "does_not_exist.sqlite3", FX)


# ---------------------------------------------------------------------------
# Command shape — structural sanity checks that don't need a DB.
# ---------------------------------------------------------------------------


class TestCommandShape:
    def test_models_cover_all_eight(self):
        names = [m.__name__ for m in MODELS]
        assert names == [
            "User",
            "Landlord",
            "Property",
            "Property_capital_structure",
            "Tenant",
            "Lease_rent",
            "Transaction",
            "FX",
        ]

    def test_command_exposes_expected_args(self):
        cmd = Command()
        parser = cmd.create_parser("manage.py", "migrate_sqlite_to_postgres")
        actions = {a.dest for a in parser._actions}
        assert {"sqlite_path", "skip_migrate", "dry_run"} <= actions

    def test_dry_run_does_not_touch_destination(self, tmp_path, capsys):
        """``--dry-run`` must only read the source and print; never insert."""
        # Build a tiny source so the read loop has something to count.
        # We populate ONLY the FX table; the dry-run code path reads each
        # model's table in turn, so for the other 7 models we stub the
        # reader to return an empty list rather than letting it crash on
        # missing tables. This keeps the test focused on the dry-run
        # contract (no writes) rather than on building a full schema.
        sqlite_path = tmp_path / "src.sqlite3"
        conn = sqlite3.connect(str(sqlite_path))
        conn.executescript(
            """
            CREATE TABLE rentals_fx (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                from_currency TEXT NOT NULL,
                to_currency TEXT NOT NULL,
                rate NUMERIC NOT NULL
            );
            INSERT INTO rentals_fx VALUES (1, '2024-01-01', 'EUR', 'USD', 1.1);
            """
        )
        conn.commit()
        conn.close()

        # Stub read_sqlite_rows so every non-FX model returns ([], []). For
        # FX we let the real reader run against the temp DB above.
        from rentals.management.commands import migrate_sqlite_to_postgres as mod

        real_reader = mod.read_sqlite_rows

        def _stub(path, model):
            if model.__name__ == "FX":
                return real_reader(path, model)
            return [], []

        # Spy on bulk_create so we can assert it was NEVER called.
        with mock.patch.object(mod, "read_sqlite_rows", side_effect=_stub), \
             mock.patch.object(mod, "call_command") as mock_migrate, \
             mock.patch.object(FX.objects, "bulk_create") as mock_bulk:
            call_command(
                "migrate_sqlite_to_postgres",
                sqlite_path=str(sqlite_path),
                dry_run=True,
            )
            mock_migrate.assert_not_called()
            mock_bulk.assert_not_called()

        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "FX: sqlite=1 rows" in out


# ---------------------------------------------------------------------------
# End-to-end against the project's db.sqlite3 (best-effort).
# Only runs if db.sqlite3 exists at the project root. The dry-run path
# is read-only, so it's safe regardless of the destination backend.
# ---------------------------------------------------------------------------


def test_dry_run_smoke_against_project_db(capsys):
    """If the project ships a ``db.sqlite3``, the dry-run should work.

    Skip silently when it's absent — the migration script is still correct;
    this just guards against the SQLite-read path regressing on the real
    schema.
    """
    from django.conf import settings

    sqlite_path = Path(settings.BASE_DIR) / "db.sqlite3"
    if not sqlite_path.exists():
        pytest.skip("No project db.sqlite3 present; skipping live-read smoke.")

    call_command("migrate_sqlite_to_postgres", dry_run=True)
    out = capsys.readouterr().out
    # Every model should at least be mentioned, even if its count is 0.
    # Covers all 8 rentals tables — the dry-run iterates MODELS in full.
    for name in (
        "User",
        "Landlord",
        "Property",
        "Property_capital_structure",
        "Tenant",
        "Lease_rent",
        "Transaction",
        "FX",
    ):
        assert name in out
