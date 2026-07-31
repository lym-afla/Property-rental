from django.db import migrations


def canonicalize_other_income(apps, schema_editor):
    Transaction = apps.get_model("rentals", "Transaction")
    Transaction.objects.filter(category="other_income").update(
        category="cost_reimbursement",
        type="expense",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("rentals", "0021_alter_transaction_category"),
    ]

    operations = [
        migrations.RunPython(
            canonicalize_other_income,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
