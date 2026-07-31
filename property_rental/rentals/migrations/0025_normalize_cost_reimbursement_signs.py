from decimal import Decimal

from django.db import migrations


def normalize_cost_reimbursements(apps, schema_editor):
    Transaction = apps.get_model("rentals", "Transaction")
    for transaction in Transaction.objects.filter(category="cost_reimbursement"):
        transaction.amount = abs(transaction.amount or Decimal("0"))
        transaction.type = "expense"
        transaction.save(update_fields=["amount", "type"])


def reverse_normalize_cost_reimbursements(apps, schema_editor):
    Transaction = apps.get_model("rentals", "Transaction")
    Transaction.objects.filter(category="cost_reimbursement").update(type="expense")


class Migration(migrations.Migration):
    dependencies = [
        ("rentals", "0024_fx_rate_identity"),
    ]

    operations = [
        migrations.RunPython(
            normalize_cost_reimbursements,
            reverse_normalize_cost_reimbursements,
        ),
    ]
