"""Validate and atomically import a single loan's dated mortgage payments."""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rentals.api.serializers import LoanPaymentSerializer
from rentals.models import Loan
from rentals.services.loans import record_payment


class Command(BaseCommand):
    help = 'Import date,interest,total (or principal) CSV rows for a loan; no historical amounts are inferred.'

    def add_arguments(self, parser):
        parser.add_argument('--loan', type=int, required=True)
        parser.add_argument('--file', required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            loan = Loan.objects.get(pk=options['loan'])
        except Loan.DoesNotExist:
            raise CommandError('Loan not found.')
        rows = []
        seen = set()
        try:
            with Path(options['file']).open(encoding='utf-8-sig', newline='') as source:
                reader = csv.DictReader(source)
                if not reader.fieldnames or not {'date', 'interest'} <= set(reader.fieldnames):
                    raise CommandError('CSV needs date,interest,total or date,interest,principal headers.')
                allowed = {'date', 'interest', 'total', 'principal', 'comment', 'period'}
                if set(reader.fieldnames) - allowed or len(reader.fieldnames) != len(set(reader.fieldnames)):
                    raise CommandError('Unknown or duplicate CSV columns.')
                for number, row in enumerate(reader, start=2):
                    if None in row or any(value is None for value in row.values()):
                        raise CommandError(f'Row {number}: wrong number of columns.')
                    serializer = LoanPaymentSerializer(data={key: value for key, value in row.items() if value != ''})
                    if not serializer.is_valid():
                        raise CommandError(f'Row {number}: {serializer.errors}')
                    values = serializer.validated_data
                    key = (values['date'], values['interest'], values['principal'])
                    if key in seen:
                        raise CommandError(f'Row {number}: duplicate payment in CSV.')
                    seen.add(key)
                    rows.append((number, values))
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f'Cannot read payment CSV: {exc}') from exc
        if not rows:
            raise CommandError('CSV has no payment rows.')
        with transaction.atomic():
            loan = Loan.objects.select_for_update().get(pk=loan.pk)
            for number, values in rows:
                # A partial previous import must be reviewed rather than
                # silently duplicating either side of the mortgage payment.
                if any(loan.transactions.filter(date=values['date'], category=category, amount=values[field]).exists()
                       for category, field in (('loan_interest', 'interest'), ('loan_principal', 'principal'))):
                    raise CommandError(f'Row {number}: a matching payment component already exists; review the ledger.')
            if not options['dry_run']:
                for _, values in rows:
                    record_payment(loan, **values)
        self.stdout.write(f'{"Validated" if options["dry_run"] else "Imported"} {len(rows)} payments for loan {loan.pk}.')
