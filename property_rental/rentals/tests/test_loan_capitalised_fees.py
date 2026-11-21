from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import RestrictedError

from rentals import models
from rentals.analytics.cash_flow import portfolio_cash_flow
from rentals.analytics.pnl import profit_and_loss
from rentals.tests.factories import PropertyFactory, PropertyCapitalStructureFactory
from rentals.tests.test_loan_reports import END, filters_for
from rentals.tests.test_loans import make_loan

pytestmark = pytest.mark.django_db
ENDPOINT = '/api/v1/loan-capitalised-fees/'


def fee(loan, day, amount='999'):
    return models.LoanCapitalisedFee.objects.create(
        loan=loan, date=date(2026, 1, day), amount=Decimal(amount),
        description='Product switch fee',
    )


def test_fee_reconciliation_boundaries_and_once_only(auth_client, sample_property):
    loan = make_loan(sample_property)
    for day, debt in ((1, '1000'), (10, '1899'), (20, '1804')):
        PropertyCapitalStructureFactory(property=sample_property, loan=loan,
            capital_structure_date=date(2026, 1, day), capital_structure_debt=debt)
    fee(loan, 1, '250')  # Already included in the opening observation.
    fee(loan, 10)
    fee(loan, 11, '5')
    fee(loan, 21, '700')  # Outside both intervals.
    fee(make_loan(sample_property), 10, '500')
    for day in (10, 20):
        models.Transaction.objects.create(property=sample_property, loan=loan, currency='USD',
            date=date(2026, 1, day), category='loan_principal', amount=Decimal('100'))
    rows = auth_client.get(f'/api/v1/loans/{loan.pk}/reconciliation/').json()
    assert [Decimal(row['capitalised_fees']) for row in rows] == [999, 5]
    assert [Decimal(row['expected_closing_debt']) for row in rows] == [1899, 1804]
    assert not any(row['flagged'] for row in rows)


def test_fee_crud_scope_and_validation(auth_client, sample_property):
    loan = make_loan(sample_property)
    foreign = make_loan(PropertyFactory())
    payload = {'loan': loan.pk, 'date': '2026-01-10', 'amount': '999', 'description': 'Product fee'}
    response = auth_client.post(ENDPOINT, payload)
    assert response.status_code == 201
    row = response.json()
    assert row['property'] == sample_property.pk
    assert row['created_at'] and row['updated_at']
    endpoint = f'{ENDPOINT}{row["id"]}/'
    assert auth_client.patch(endpoint, {'amount': '1000'}, content_type='application/json').status_code == 200
    for amount in ('0', '-1', 'NaN', '1.001'):
        assert auth_client.post(ENDPOINT, {**payload, 'amount': amount}).status_code == 400
    assert auth_client.post(ENDPOINT, {**payload, 'loan': foreign.pk}).status_code in (400, 404)
    assert auth_client.patch(endpoint, {'loan': foreign.pk}, content_type='application/json').status_code in (400, 404)
    foreign_fee = fee(foreign, 10)
    for method in ('get', 'delete'):
        assert getattr(auth_client, method)(f'{ENDPOINT}{foreign_fee.pk}/').status_code == 404
    rows = auth_client.get(ENDPOINT, {'loan': loan.pk}).json()
    assert [r['id'] for r in rows] == [row['id']]
    assert auth_client.get(ENDPOINT, {'loan': foreign.pk}).json() == []
    assert auth_client.get(ENDPOINT, {'property': foreign.property_id}).json() == []
    assert auth_client.delete(endpoint).status_code == 204


def test_fee_protects_loan_but_property_cascades(auth_client, sample_property):
    loan = make_loan(sample_property)
    row = fee(loan, 10)
    with pytest.raises(RestrictedError):
        loan.delete()
    assert auth_client.delete(f'/api/v1/loans/{loan.pk}/').status_code == 400
    other = PropertyFactory(owned_by=sample_property.owned_by)
    loan.property = other
    with pytest.raises(ValidationError):
        loan.save()
    sample_property.delete()
    assert not models.LoanCapitalisedFee.objects.filter(pk=row.pk).exists()


def test_fee_has_no_cash_flow_or_profit_effect(landlord_user, sample_property):
    loan = make_loan(sample_property)
    cash_before = portfolio_cash_flow(landlord_user, filters_for())
    pnl_before = profit_and_loss(landlord_user, END, 'USD')
    fee(loan, 10)
    assert models.Transaction.objects.filter(loan=loan).count() == 0
    assert portfolio_cash_flow(landlord_user, filters_for()) == cash_before
    assert profit_and_loss(landlord_user, END, 'USD') == pnl_before


def test_fee_model_rejects_zero_and_negative_amounts(sample_property):
    loan = make_loan(sample_property)
    for amount in ('0', '-0.01'):
        with pytest.raises(ValidationError):
            fee(loan, 10, amount)


def test_capitalised_fee_is_absent_from_wealth_transactions(landlord_user, sample_property):
    from rentals.services.wealth_export import build_wealth_export

    models.OIDCIdentity.objects.create(user=landlord_user, subject="fee-owner", issuer="https://auth.example/")
    loan = make_loan(sample_property)
    PropertyCapitalStructureFactory(property=sample_property, loan=loan,
        capital_structure_date=date(2026, 1, 1), capital_structure_value=Decimal("2000"),
        capital_structure_debt=Decimal("1000"))
    before = build_wealth_export(subject="fee-owner", as_of=END)
    fee(loan, 10)
    after = build_wealth_export(subject="fee-owner", as_of=END)
    assert after["transactions"] == before["transactions"] == []
    assert after["capital_observations"] == before["capital_observations"]


def test_fee_cannot_spoof_property_and_can_precede_product_start(auth_client, sample_property):
    loan = make_loan(sample_property)
    loan.start_date = date(2026, 4, 1)
    loan.save()
    foreign = PropertyFactory()
    response = auth_client.post(ENDPOINT, {
        'loan': loan.pk, 'property': foreign.pk, 'date': '2026-03-31', 'amount': '999',
    })
    assert response.status_code == 201
    assert response.json()['property'] == sample_property.pk
    row = models.LoanCapitalisedFee.objects.get(pk=response.json()['id'])
    assert row.property_id == loan.property_id


@pytest.mark.parametrize('field', ['loan', 'property'])
@pytest.mark.parametrize('value', ['bogus', '1.5', '0', '-1', '', '999999999999999999999999999'])
def test_fee_query_filter_rejects_invalid_ids(auth_client, field, value):
    response = auth_client.get(ENDPOINT, {field: value})
    assert response.status_code == 400
    assert field in response.json()


def test_fee_same_owner_loan_change_updates_property(auth_client, sample_property):
    loan = make_loan(sample_property)
    row = fee(loan, 10)
    other_property = PropertyFactory(owned_by=sample_property.owned_by)
    other_loan = make_loan(other_property)
    response = auth_client.patch(f'{ENDPOINT}{row.pk}/', {'loan': other_loan.pk}, content_type='application/json')
    assert response.status_code == 200
    assert response.json()['loan'] == other_loan.pk
    assert response.json()['property'] == other_property.pk
    row.refresh_from_db()
    assert row.property_id == other_property.pk
    assert auth_client.get(ENDPOINT, {'loan': loan.pk}).json() == []
    assert [item['id'] for item in auth_client.get(ENDPOINT, {'property': other_property.pk}).json()] == [row.pk]
