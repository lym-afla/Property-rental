from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_legacy_loan_terms_copied_without_financial_changes():
    executor = MigrationExecutor(connection)
    before = [('rentals', '0031_loancapitalisedfee_and_more')]
    after = executor.loader.graph.leaf_nodes('rentals')
    try:
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        user = apps.get_model('rentals', 'User').objects.create(username='product-upgrade')
        owner = apps.get_model('rentals', 'Landlord').objects.create(user=user)
        prop = apps.get_model('rentals', 'Property').objects.create(
            owned_by=owner, name='Property', location='City', num_bedrooms=1, currency='GBP')
        Loan = apps.get_model('rentals', 'Loan')
        known = Loan.objects.create(property=prop, lender='Test bank', currency='GBP',
            start_date=date(2020, 1, 1), end_date=date(2021, 12, 31),
            interest_rate=Decimal('3.2500'), rate_type='fixed', original_principal=Decimal('12345.67'))
        unknown = Loan.objects.create(property=prop, lender='Other bank', currency='GBP', start_date=date(2010, 1, 1))
        Capital = apps.get_model('rentals', 'Property_capital_structure')
        Capital.objects.create(property=prop, loan=known, capital_structure_date=date(2021, 1, 1),
                               capital_structure_debt=Decimal('12000'))
        snapshots = {name: list(apps.get_model('rentals', name).objects.values()) for name in
                     ('Loan', 'Property_capital_structure', 'Transaction', 'LoanCapitalisedFee')}
        executor = MigrationExecutor(connection)
        executor.migrate(after)
        apps = executor.loader.project_state(after).apps
        Product = apps.get_model('rentals', 'LoanProduct')
        assert Product.objects.count() == 2
        product = Product.objects.get(loan_id=known.pk)
        assert product.name == 'Recorded mortgage product'
        assert product.lender == known.lender
        assert product.start_date == known.start_date
        assert product.end_date == known.end_date
        assert product.interest_rate == known.interest_rate
        assert product.rate_type == known.rate_type
        assert product.opening_balance == known.original_principal
        assert 'Copied' in product.notes
        assert product.created_at and product.updated_at
        empty = Product.objects.get(loan_id=unknown.pk)
        assert empty.opening_balance is None and empty.interest_rate is None
        assert empty.rate_type == '' and empty.end_date is None
        for name, rows in snapshots.items():
            assert list(apps.get_model('rentals', name).objects.values()) == rows
    finally:
        MigrationExecutor(connection).migrate(after)
