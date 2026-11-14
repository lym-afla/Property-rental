from django.db import migrations
from django.db.models import Min


def backfill_loans(apps, schema_editor):
    Capital = apps.get_model('rentals', 'Property_capital_structure')
    Loan = apps.get_model('rentals', 'Loan')
    Property = apps.get_model('rentals', 'Property')
    alias = schema_editor.connection.alias
    property_ids = Capital.objects.using(alias).filter(
        capital_structure_debt__isnull=False,
    ).exclude(capital_structure_debt=0).values_list('property_id', flat=True).distinct()
    for prop in Property.objects.using(alias).filter(pk__in=property_ids).order_by('pk'):
        if Loan.objects.using(alias).filter(property_id=prop.pk).exists():
            continue
        observations = Capital.objects.using(alias).filter(property_id=prop.pk)
        start = observations.aggregate(first=Min('capital_structure_date'))['first']
        loan = Loan.objects.using(alias).create(
            property_id=prop.pk, lender='UNKNOWN — fill in',
            currency=prop.currency, start_date=start,
        )
        observations.filter(capital_structure_debt__isnull=False).update(loan_id=loan.pk)
        print(f'Loan {loan.pk}: property_id={prop.pk}; lender UNKNOWN — fill in')


def reverse_backfill(apps, schema_editor):
    # Preserve operator edits: rolling back the following schema migration
    # removes the loans table and references, so no broad data deletion here.
    pass


class Migration(migrations.Migration):
    dependencies = [('rentals', '0029_depositmovement_created_at_and_more')]
    operations = [migrations.RunPython(backfill_loans, reverse_backfill)]
