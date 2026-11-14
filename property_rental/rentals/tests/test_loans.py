from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from rentals import models
from rentals.tests.factories import PropertyFactory, PropertyCapitalStructureFactory

pytestmark = pytest.mark.django_db


def make_loan(prop, **kwargs):
    return models.Loan.objects.create(
        property=prop, lender='Bank', currency=prop.currency,
        start_date=date(2025, 1, 1), **kwargs,
    )


def test_loan_currency_and_dates(sample_property):
    loan = make_loan(sample_property)
    loan.currency = 'GBP'
    with pytest.raises(ValidationError):
        loan.full_clean()
    loan.currency = sample_property.currency
    loan.end_date = date(2024, 1, 1)
    with pytest.raises(ValidationError):
        loan.full_clean()


def test_new_debt_requires_same_property_loan(auth_client, sample_property):
    payload = {'property': sample_property.pk, 'capital_structure_date': '2025-01-01',
               'capital_structure_value': '2000', 'capital_structure_debt': '1000'}
    response = auth_client.post('/api/v1/property-valuations/', payload)
    assert response.status_code == 400
    loan = make_loan(sample_property)
    response = auth_client.post('/api/v1/property-valuations/', {**payload, 'loan': loan.pk})
    assert response.status_code == 201
    other = PropertyFactory(owned_by=sample_property.owned_by)
    response = auth_client.patch(f'/api/v1/property-valuations/{response.json()["id"]}/',
                                 {'property': other.pk}, content_type='application/json')
    assert response.status_code == 400


def test_loan_crud_and_owner_scope(auth_client, sample_property):
    response = auth_client.post('/api/v1/loans/', {
        'property': sample_property.pk, 'lender': 'Bank', 'currency': 'USD',
        'start_date': '2025-01-01',
    })
    assert response.status_code == 201
    foreign = make_loan(PropertyFactory())
    assert auth_client.get(f'/api/v1/loans/{foreign.pk}/').status_code == 404
    assert auth_client.patch(f'/api/v1/loans/{response.json()["id"]}/',
                             {'property': foreign.property_id}, content_type='application/json').status_code in (400, 404)


def test_payment_split_is_positive_and_atomic(auth_client, sample_property):
    loan = make_loan(sample_property)
    endpoint = f'/api/v1/loans/{loan.pk}/payments/'
    response = auth_client.post(endpoint, {'date': '2025-02-01', 'total': '100.10', 'interest': '20.01'})
    assert response.status_code == 201
    interest, principal = models.Transaction.objects.filter(loan=loan).order_by('id')
    assert (interest.category, interest.amount, interest.type) == ('loan_interest', Decimal('20.01'), 'expense')
    assert (principal.category, principal.amount, principal.type) == ('loan_principal', Decimal('80.09'), 'balance_sheet')
    for invalid in (
        {'total': '10', 'interest': '11'}, {'interest': '-1', 'principal': '2'},
        {'total': '10', 'interest': '1', 'principal': '9'}, {'interest': '1'},
        {'interest': 'NaN', 'principal': '1'}, {'interest': '1.001', 'principal': '2'},
    ):
        assert auth_client.post(endpoint, {'date': '2025-02-01', **invalid}).status_code == 400
    assert models.Transaction.objects.filter(loan=loan).count() == 2


def test_transaction_requires_loan_and_validates_partial_updates(auth_client, sample_property):
    payload = {'property': sample_property.pk, 'date': '2025-02-01', 'category': 'loan_interest',
               'amount': '20', 'currency': 'USD'}
    assert auth_client.post('/api/v1/transactions/', payload).status_code == 400
    loan = make_loan(sample_property)
    response = auth_client.post('/api/v1/transactions/', {**payload, 'loan': loan.pk})
    assert response.status_code == 201
    endpoint = f'/api/v1/transactions/{response.json()["id"]}/'
    assert auth_client.patch(endpoint, {'currency': 'GBP'}, content_type='application/json').status_code == 400
    assert auth_client.patch(endpoint, {'loan': None}, content_type='application/json').status_code == 400
    assert auth_client.patch(endpoint, {'loan': make_loan(PropertyFactory()).pk}, content_type='application/json').status_code == 400


def test_reconciliation_uses_open_exclusive_close_inclusive_and_tolerance(auth_client, sample_property):
    loan = make_loan(sample_property)
    for day, balance in ((1, '1000'), (10, '900'), (20, '801'), (25, '699')):
        PropertyCapitalStructureFactory(property=sample_property, loan=loan,
            capital_structure_date=date(2025, 1, day), capital_structure_debt=balance)
    for day in (1, 10, 20, 25):
        models.Transaction.objects.create(property=sample_property, loan=loan, currency='USD',
            date=date(2025, 1, day), category='loan_principal', amount=Decimal('100'))
    response = auth_client.get(f'/api/v1/loans/{loan.pk}/reconciliation/')
    assert response.status_code == 200
    rows = response.json()
    assert [row['flagged'] for row in rows] == [False, False, True]
    assert Decimal(rows[0]['principal_paid']) == 100


def test_timestamp_changes_on_edit(sample_property):
    created, updated = sample_property.created_at, sample_property.updated_at
    sample_property.name = 'Updated'
    sample_property.save()
    sample_property.refresh_from_db()
    assert sample_property.created_at == created
    assert sample_property.updated_at > updated


def test_unlinked_zero_payoff_is_reconciled(auth_client, sample_property):
    loan = make_loan(sample_property)
    PropertyCapitalStructureFactory(property=sample_property, loan=loan,
        capital_structure_date=date(2025, 1, 1), capital_structure_debt=Decimal('1000'))
    PropertyCapitalStructureFactory(property=sample_property,
        capital_structure_date=date(2025, 2, 1), capital_structure_debt=Decimal('0'))
    response = auth_client.get(f'/api/v1/loans/{loan.pk}/reconciliation/')
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]['flagged'] is True
    assert Decimal(response.json()[0]['closing_debt']) == 0


def test_ambiguous_unlinked_payoff_needs_explicit_loan(auth_client, sample_property):
    loans = [make_loan(sample_property) for _ in range(2)]
    for loan in loans:
        PropertyCapitalStructureFactory(property=sample_property, loan=loan,
            capital_structure_date=date(2025, 1, 1), capital_structure_debt=Decimal('1000'))
    PropertyCapitalStructureFactory(property=sample_property,
        capital_structure_date=date(2025, 2, 1), capital_structure_debt=Decimal('0'))
    response = auth_client.get(f'/api/v1/loans/{loans[0].pk}/reconciliation/')
    assert response.status_code == 400


@pytest.mark.parametrize('debt_payload', [{}, {'capital_structure_debt': None}, {'capital_structure_debt': ''}])
def test_valuation_only_does_not_invent_loan_payoff(auth_client, sample_property, debt_payload):
    response = auth_client.post('/api/v1/property-valuations/', {
        'property': sample_property.pk, 'capital_structure_date': '2025-01-01',
        'capital_structure_value': '2000', **debt_payload,
    }, content_type='application/json')
    assert response.status_code == 201
    assert response.json()['capital_structure_debt'] is None


def test_loan_history_blocks_loan_deletion_but_property_cascade_still_works(auth_client, sample_property):
    loan = make_loan(sample_property)
    PropertyCapitalStructureFactory(property=sample_property, loan=loan,
        capital_structure_debt=Decimal('1000'))
    assert auth_client.delete(f'/api/v1/loans/{loan.pk}/').status_code == 400
    assert auth_client.delete(f'/api/v1/properties/{sample_property.pk}/').status_code == 204
