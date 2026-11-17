from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from rentals import models
from rentals.tests.factories import PropertyFactory, PropertyCapitalStructureFactory
from rentals.tests.test_loans import make_loan
from rentals.tests.test_loan_reports import END, filters_for

pytestmark = pytest.mark.django_db
URL = '/api/v1/loan-products/'


def payload(loan, **overrides):
    return dict(loan=loan.pk, name='Fixed product', lender='Lender', start_date='2020-01-01',
                end_date='2021-12-31', interest_rate='2.5', rate_type='fixed',
                opening_balance='1000', notes='', **overrides)


def test_products_crud_owner_scope_and_immutable_loan(auth_client, sample_property):
    loan = make_loan(sample_property)
    foreign = make_loan(PropertyFactory())
    response = auth_client.post(URL, payload(loan))
    assert response.status_code == 201
    row = response.json()
    assert set(row) == {'id', 'loan', 'name', 'lender', 'start_date', 'end_date', 'interest_rate',
                        'rate_type', 'opening_balance', 'notes', 'created_at', 'updated_at'}
    detail = f'{URL}{row["id"]}/'
    assert auth_client.patch(detail, {'notes': 'Source offer'}, content_type='application/json').status_code == 200
    other = make_loan(sample_property)
    for target in (foreign, other):
        assert auth_client.patch(detail, {'loan': target.pk}, content_type='application/json').status_code == 400
    assert auth_client.post(URL, payload(foreign)).status_code == 400
    hidden = models.LoanProduct.objects.create(**{**payload(foreign), 'loan': foreign})
    for method in ('get', 'delete'):
        assert getattr(auth_client, method)(f'{URL}{hidden.pk}/').status_code == 404
    assert auth_client.patch(f'{URL}{hidden.pk}/', {'notes': 'x'}, content_type='application/json').status_code == 404
    assert auth_client.get(URL, {'loan': foreign.pk}).json() == []
    assert auth_client.get(URL, {'property': foreign.property_id}).json() == []
    assert [r['id'] for r in auth_client.get(URL, {'property': sample_property.pk}).json()] == [row['id']]
    assert auth_client.delete(detail).status_code == 204


def test_product_inclusive_overlap_and_partial_update(auth_client, sample_property):
    loan = make_loan(sample_property)
    first = auth_client.post(URL, payload(loan)).json()
    for start, end in [('2021-12-31', '2023-01-01'), ('2019-01-01', '2020-01-01'),
                       ('2020-06-01', '2020-07-01'), ('2019-01-01', None)]:
        data = payload(loan)
        data.update(start_date=start, end_date=end)
        assert auth_client.post(URL, data, content_type='application/json').status_code == 400
    data = payload(loan)
    data.update(start_date='2022-01-01', end_date=None, interest_rate=None, rate_type='')
    second = auth_client.post(URL, data, content_type='application/json')
    assert second.status_code == 201
    assert auth_client.patch(f'{URL}{first["id"]}/', {'end_date': '2022-01-01'}, content_type='application/json').status_code == 400
    assert auth_client.patch(f'{URL}{second.json()["id"]}/', {'start_date': '2021-12-01'}, content_type='application/json').status_code == 400
    assert auth_client.patch(f'{URL}{first["id"]}/', {'name': 'Updated'}, content_type='application/json').status_code == 200
    assert [r['id'] for r in auth_client.get(URL, {'loan': loan.pk}).json()] == [first['id'], second.json()['id']]


@pytest.mark.parametrize('field,value', [('name', '  '), ('lender', ' '), ('rate_type', ''),
    ('end_date', '2019-01-01'), ('interest_rate', '-1'), ('interest_rate', 'NaN'),
    ('interest_rate', 'Infinity'), ('opening_balance', '-1'), ('opening_balance', 'NaN'),
    ('opening_balance', 'Infinity'), ('notes', 'x' * 2001)])
def test_product_invalid_fields(auth_client, sample_property, field, value):
    data = payload(make_loan(sample_property))
    data[field] = value
    response = auth_client.post(URL, data)
    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.parametrize('field', ['loan', 'property'])
@pytest.mark.parametrize('value', ['bogus', '1.5', '0', '-1', '', '99999999999999999999999999'])
def test_product_invalid_filters(auth_client, field, value):
    response = auth_client.get(URL, {field: value})
    assert response.status_code == 400
    assert field in response.json()


def test_product_edits_preserve_financial_outputs(auth_client, landlord_user, sample_property):
    from rentals.analytics.cash_flow import portfolio_cash_flow
    from rentals.analytics.pnl import profit_and_loss
    from rentals.services.loans import reconcile_loan
    from rentals.services.wealth_export import build_wealth_export
    models.OIDCIdentity.objects.create(user=landlord_user, subject='product-owner', issuer='https://auth.example/')
    loan = make_loan(sample_property)
    PropertyCapitalStructureFactory(property=sample_property, loan=loan,
        capital_structure_date=date(2026, 1, 1), capital_structure_value=2000, capital_structure_debt=1000)
    models.Transaction.objects.create(property=sample_property, loan=loan, currency='USD',
        date=date(2026, 1, 10), category='loan_principal', amount=Decimal('100'))
    def snapshot():
        export = build_wealth_export(subject='product-owner', as_of=END)
        export.pop('generated_at')
        return (portfolio_cash_flow(landlord_user, filters_for()), profit_and_loss(landlord_user, END, 'USD'),
                reconcile_loan(loan), export,
                list(models.Transaction.objects.values()), list(models.Property_capital_structure.objects.values()),
                list(models.LoanCapitalisedFee.objects.values()), list(models.Loan.objects.values()))
    before = snapshot()
    response = auth_client.post(URL, payload(loan))
    assert response.status_code == 201
    detail = f'{URL}{response.json()["id"]}/'
    assert snapshot() == before
    assert auth_client.patch(detail, {'interest_rate': '7.1'}, content_type='application/json').status_code == 200
    assert snapshot() == before
    assert auth_client.delete(detail).status_code == 204
    assert snapshot() == before


def test_product_optional_terms_zero_and_trimming(auth_client, sample_property):
    data = payload(make_loan(sample_property))
    data.update(name='  Historical tracker  ', lender='  Test bank  ', interest_rate=None,
                rate_type='', opening_balance='0', end_date=None)
    response = auth_client.post(URL, data, content_type='application/json')
    assert response.status_code == 201
    assert response.json()['name'] == 'Historical tracker'
    assert response.json()['lender'] == 'Test bank'
    assert response.json()['interest_rate'] is None
    assert response.json()['opening_balance'] == '0.00'


def test_product_requires_authentication(client):
    assert client.get(URL).status_code in (401, 403)


@pytest.mark.django_db(transaction=True)
def test_concurrent_overlapping_products_are_serialized(sample_property):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection, connections

    if connection.vendor != 'postgresql':
        pytest.skip('Row-lock concurrency requires PostgreSQL')
    loan = make_loan(sample_property)
    barrier = Barrier(2)

    def save_product():
        try:
            barrier.wait(timeout=10)
            models.LoanProduct.objects.create(loan_id=loan.pk, name='Concurrent switch', lender='Test bank',
                start_date=date(2020, 1, 1), end_date=date(2021, 12, 31))
            return 'created'
        except ValidationError:
            return 'overlap'
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: save_product(), range(2)))
    assert sorted(results) == ['created', 'overlap']
    assert models.LoanProduct.objects.filter(loan=loan).count() == 1
