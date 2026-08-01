from django.db import migrations
from django.db.models import F


def normalize_legacy_predated_lease_rent_currency(apps, schema_editor):
    LeaseRent = apps.get_model("rentals", "Lease_rent")
    Transaction = apps.get_model("rentals", "Transaction")

    candidates = (
        LeaseRent.objects.select_related("tenant", "tenant__property")
        .filter(date_rent_set__lt=F("tenant__lease_start"))
        .exclude(currency=F("tenant__property__currency"))
        .exclude(currency__isnull=True)
        .exclude(currency="")
        .exclude(tenant__property__currency__isnull=True)
        .exclude(tenant__property__currency="")
    )
    for rent in candidates.iterator():
        tenant = rent.tenant
        property_currency = tenant.property.currency
        has_matching_native_receipt = Transaction.objects.filter(
            property_id=tenant.property_id,
            tenant_id=tenant.id,
            category="rent",
            date__gte=tenant.lease_start,
            amount=rent.rent,
            currency=property_currency,
        ).exists()
        if has_matching_native_receipt:
            rent.currency = property_currency
            rent.save(update_fields=["currency"])


class Migration(migrations.Migration):
    dependencies = [
        ("rentals", "0025_normalize_cost_reimbursement_signs"),
    ]

    operations = [
        migrations.RunPython(
            normalize_legacy_predated_lease_rent_currency,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
