from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command, CommandError

from rentals.models import Transaction
from rentals.tests.test_loans import make_loan

pytestmark = pytest.mark.django_db


def test_payment_csv_validates_all_before_writing_and_supports_dry_run(tmp_path, sample_property):
    loan = make_loan(sample_property)
    path = tmp_path / 'payments.csv'
    path.write_text('date,total,interest\n2025-01-01,100.10,20.01\n2025-02-01,100.10,19.01\n')
    call_command('import_loan_payments', loan=loan.pk, file=str(path), dry_run=True)
    assert not Transaction.objects.exists()
    call_command('import_loan_payments', loan=loan.pk, file=str(path))
    assert Transaction.objects.filter(loan=loan).count() == 4
    assert sum(Transaction.objects.filter(category='loan_principal').values_list('amount', flat=True)) == Decimal('161.18')
    with pytest.raises(CommandError, match='already exists'):
        call_command('import_loan_payments', loan=loan.pk, file=str(path))
    path.write_text('date,interest,principal\n2025-03-01,18,82\n2025-04-01,-1,80\n')
    with pytest.raises(CommandError):
        call_command('import_loan_payments', loan=loan.pk, file=str(path))
    assert Transaction.objects.filter(loan=loan).count() == 4
