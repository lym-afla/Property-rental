"""Atomic mortgage payments and checks against dated loan balances."""

from decimal import Decimal

from django.db import transaction

from rentals.models import Loan, Transaction


@transaction.atomic
def record_payment(loan, *, date, interest, principal, comment='', period=''):
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    return [
        Transaction.objects.create(
            property=loan.property, loan=loan, currency=loan.currency,
            date=date, category=category, amount=amount, comment=comment,
            period=period or date.strftime('%Y-%m'),
        )
        for category, amount in (("loan_interest", interest), ("loan_principal", principal))
    ]


def reconcile_loan(loan):
    observations = loan.property.capital.exclude(
        capital_structure_debt__isnull=True,
    ).order_by('capital_structure_date', 'id')
    balances = {}
    by_date = {}
    for row in observations:
        source_loan = row.loan_id
        if source_loan is None and row.capital_structure_debt == 0:
            outstanding = [key for key, value in balances.items() if value != 0]
            if len(outstanding) > 1 and loan.pk in outstanding:
                raise ValueError("A zero balance has several possible loans; link the observation to its loan.")
            if len(outstanding) == 1:
                source_loan = outstanding[0]
        if source_loan is not None:
            balances[source_loan] = row.capital_structure_debt
        if source_loan == loan.pk:
            on = row.capital_structure_date
            if on in by_date and by_date[on].capital_structure_debt != row.capital_structure_debt:
                raise ValueError("Conflicting same-day debt balances must be corrected before reconciliation.")
            by_date[on] = row
    rows = list(by_date.values())
    payments = list(loan.transactions.filter(category='loan_principal').order_by('date', 'id'))
    result = []
    for opening, closing in zip(rows, rows[1:]):
        paid = sum((p.amount.copy_abs() for p in payments
                    if opening.capital_structure_date < p.date <= closing.capital_structure_date), Decimal('0'))
        expected = opening.capital_structure_debt - paid
        difference = closing.capital_structure_debt - expected
        result.append({
            'opening_date': opening.capital_structure_date.isoformat(),
            'closing_date': closing.capital_structure_date.isoformat(),
            'opening_debt': str(opening.capital_structure_debt),
            'principal_paid': str(paid),
            'closing_debt': str(closing.capital_structure_debt),
            'expected_closing_debt': str(expected),
            'difference': str(difference),
            'flagged': abs(difference) > Decimal('1'),
        })
    return result
