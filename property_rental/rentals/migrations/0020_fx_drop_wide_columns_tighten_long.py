"""Phase 2 of the FX wide->long migration (Task 9): drop the legacy
per-pair columns and tighten the new long-format fields to non-nullable.

This migration assumes ``0019_fx_wide_to_long`` has run, i.e. every FX
row that had data in any of ``EURUSD`` / ``GBPUSD`` / ``USDRUB`` has
already been turned into one long row per non-null pair, and the
original wide row deleted. The new fields can therefore be made
non-nullable without data loss.

We still guard the null->not-null transition with a RunPython
(``cleanup_null_long_rows``) that deletes any stray FX row whose new
fields are null (defensive: if ``0019`` skipped a row for any reason,
this prevents the AlterField below from failing on the NOT NULL
constraint). The ``AlterField`` operations themselves set no
``default`` — by the time they run, the backfill in ``0019`` has
populated all remaining rows, so there are no rows left to default.
"""

from django.db import migrations, models


def cleanup_null_long_rows(apps, schema_editor):
    """Delete any FX row whose long-format fields are null before we
    enforce NOT NULL. Belt-and-suspenders: ``0019`` should already have
    populated every row, but production deployments that ran partial
    state would otherwise crash the AlterField below."""
    FX = apps.get_model("rentals", "FX")
    FX.objects.filter(from_currency__isnull=True).delete()
    FX.objects.filter(to_currency__isnull=True).delete()
    FX.objects.filter(rate__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rentals", "0019_fx_wide_to_long"),
    ]

    operations = [
        migrations.RunPython(cleanup_null_long_rows, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="fx",
            name="EURUSD",
        ),
        migrations.RemoveField(
            model_name="fx",
            name="GBPUSD",
        ),
        migrations.RemoveField(
            model_name="fx",
            name="USDRUB",
        ),
        migrations.AlterField(
            model_name="fx",
            name="from_currency",
            field=models.CharField(max_length=3),
        ),
        migrations.AlterField(
            model_name="fx",
            name="rate",
            field=models.DecimalField(decimal_places=10, max_digits=20),
        ),
        migrations.AlterField(
            model_name="fx",
            name="to_currency",
            field=models.CharField(max_length=3),
        ),
    ]
