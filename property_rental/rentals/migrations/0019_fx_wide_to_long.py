"""Wide->long data migration for the FX table (Task 9).

Companion to ``0018_fx_from_currency_fx_rate_fx_to_currency``. That
migration added the new long-format columns (nullable). This migration
backfills them from the existing per-pair columns and then removes the
old wide rows so the follow-up schema migration can drop the per-pair
columns cleanly.

For each existing FX row, emit one long row per non-null pair column:

    EURUSD -> (from_currency='EUR', to_currency='USD', rate=<EURUSD>)
    GBPUSD -> (from_currency='GBP', to_currency='USD', rate=<GBPUSD>)
    USDRUB -> (from_currency='USD', to_currency='RUB', rate=<USDRUB>)

The (from, to) directionality of each backfilled pair mirrors what the
pre-migration ``get_rate`` graph builder assumed: it parsed the column
name as ``base + quote`` (e.g. ``EURUSD`` -> base ``EUR``, quote
``USD``), and the ``element.find(i_source) == 0`` direction check
treated that order as ``source-first``. So storing ``from_currency=EUR,
to_currency=USD`` preserves the exact same edge semantics that the
wide-schema graph builder produced.

After backfilling, the old wide row is deleted (its data now lives in
the per-pair long rows). A later migration drops the now-unused pair
columns from the schema.
"""

from django.db import migrations


# (old_column, base, quote) — base+quote == the column name verbatim.
PAIR_COLUMNS = [
    ("EURUSD", "EUR", "USD"),
    ("GBPUSD", "GBP", "USD"),
    ("USDRUB", "USD", "RUB"),
]


def forwards(apps, schema_editor):
    FX = apps.get_model("rentals", "FX")
    # Snapshot the old rows first because we delete them in the same
    # loop. Iterating over the queryset and mutating inside the loop is
    # fragile on some backends.
    old_rows = list(FX.objects.values("id", "date", *[c for c, _, _ in PAIR_COLUMNS]))
    for row in old_rows:
        for col, base, quote in PAIR_COLUMNS:
            rate = row.get(col)
            if rate is not None:
                FX.objects.create(
                    date=row["date"],
                    from_currency=base,
                    to_currency=quote,
                    rate=rate,
                )
    # Remove the original wide rows. Their data now lives entirely in
    # the long rows created above.
    FX.objects.filter(id__in=[r["id"] for r in old_rows]).delete()


def backwards(apps, schema_editor):
    # No-op going backwards: re-deriving wide rows from long rows is
    # lossy if extra pairs were added since. The forward migration is
    # the source of truth. Django requires a ``reverse_code`` callable
    # to mark the operation reversible; we pass ``migrations.RunPython.noop``
    # at call time instead.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("rentals", "0018_fx_from_currency_fx_rate_fx_to_currency"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
