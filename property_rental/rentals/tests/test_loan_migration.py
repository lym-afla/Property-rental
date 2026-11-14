from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_existing_debt_gets_placeholder_loan_without_invented_terms():
    executor = MigrationExecutor(connection)
    before = [('rentals', '0028_depositmovement')]
    after = executor.loader.graph.leaf_nodes('rentals')
    try:
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        user = apps.get_model('rentals', 'User').objects.create(username='loan-upgrade')
        owner = apps.get_model('rentals', 'Landlord').objects.create(user=user)
        prop = apps.get_model('rentals', 'Property').objects.create(
            owned_by=owner, name='Property', location='City', num_bedrooms=1, currency='GBP')
        Capital = apps.get_model('rentals', 'Property_capital_structure')
        for year, debt in ((2023, 0), (2024, 1000), (2025, 0)):
            Capital.objects.create(property=prop, capital_structure_date=date(year, 1, 1), capital_structure_debt=Decimal(debt))
        no_debt = apps.get_model('rentals', 'Property').objects.create(
            owned_by=owner, name='Cash property', location='City', num_bedrooms=1, currency='GBP')
        Capital.objects.create(property=no_debt, capital_structure_debt=Decimal(0))
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        apps = executor.loader.project_state(after).apps
        loans = apps.get_model('rentals', 'Loan').objects
        assert loans.filter(property_id=prop.pk).count() == 1
        loan = loans.get(property_id=prop.pk)
        assert loan.lender == 'UNKNOWN — fill in'
        assert loan.start_date == date(2023, 1, 1)
        assert loan.currency == 'GBP'
        assert loan.original_principal is None
        assert loan.interest_rate is None
        assert loan.end_date is None
        assert not loans.filter(property_id=no_debt.pk).exists()
        assert apps.get_model('rentals', 'Property_capital_structure').objects.filter(property_id=prop.pk, loan_id=loan.pk).count() == 3
        assert apps.get_model('rentals', 'Property').objects.get(pk=prop.pk).created_at is not None
    finally:
        MigrationExecutor(connection).migrate(after)
