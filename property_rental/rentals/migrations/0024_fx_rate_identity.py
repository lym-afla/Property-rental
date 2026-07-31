from decimal import Decimal

from django.db import migrations, models


def canonicalize_rates(apps, schema_editor):
    FX = apps.get_model("rentals", "FX")
    selected = {}
    for row in FX.objects.all().order_by("id"):
        if not row.rate.is_finite() or row.rate <= 0:
            continue
        original = (
            row.from_currency.strip().upper(),
            row.to_currency.strip().upper(),
        )
        left, right = sorted(original)
        rate = row.rate if (left, right) == original else Decimal(1) / row.rate
        key = (row.date, left, right)
        if key not in selected:
            selected[key] = rate
    FX.objects.all().delete()
    FX.objects.bulk_create([
        FX(date=day, from_currency=left, to_currency=right, rate=rate)
        for (day, left, right), rate in selected.items()
    ])


class Migration(migrations.Migration):
    dependencies = [("rentals", "0023_oidc_identity")]
    operations = [
        migrations.RunPython(canonicalize_rates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="fx",
            constraint=models.UniqueConstraint(fields=("date", "from_currency", "to_currency"), name="unique_fx_rate_identity"),
        ),
    ]
