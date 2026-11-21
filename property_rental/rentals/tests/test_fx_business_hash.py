from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json

import pytest

from rentals.management.commands.export_fx_comparison import business_hash
from rentals.models import DepositMovement, Loan, LoanCapitalisedFee, LoanProduct
from rentals.tests.factories import (
    LeaseRentFactory, PropertyCapitalStructureFactory, PropertyFactory,
    TenantFactory, TransactionFactory,
)


@pytest.fixture
def native_records(db):
    prop = PropertyFactory(currency='USD')
    tenant = TenantFactory(property=prop, lease_start=date(2026, 1, 1))
    loan = Loan.objects.create(property=prop, lender='Bank', currency='USD', start_date=date(2026, 1, 1))
    return [
        prop, tenant,
        TransactionFactory(property=prop, tenant=tenant, amount=Decimal('10'), currency='USD', date=date(2026, 1, 5)),
        DepositMovement.objects.create(tenant=tenant, kind='received', amount=Decimal('3'), currency='USD', date=date(2026, 1, 5)),
        LeaseRentFactory(tenant=tenant, currency='USD'),
        PropertyCapitalStructureFactory(property=prop, loan=loan, capital_structure_debt=Decimal('100')),
        loan,
        LoanProduct.objects.create(loan=loan, name='Fixed', lender='Bank', start_date=date(2026, 1, 1)),
        LoanCapitalisedFee.objects.create(loan=loan, amount=Decimal('5'), date=date(2026, 1, 5)),
    ]


@pytest.mark.parametrize('index', range(9))
def test_audit_only_save_keeps_business_hash(native_records, monkeypatch, index):
    obj = native_records[index]
    obj.refresh_from_db()
    before = type(obj).objects.values().get(pk=obj.pk)
    original = business_hash(obj)
    monkeypatch.setattr('django.utils.timezone.now', lambda: obj.updated_at + timedelta(days=1))
    obj.save()
    obj.refresh_from_db()
    after = type(obj).objects.values().get(pk=obj.pk)
    assert before['updated_at'] != after['updated_at']
    assert {key for key in before if before[key] != after[key]} == {'updated_at'}
    assert business_hash(obj) == original


@pytest.mark.parametrize('field,value', [('amount', Decimal('11')), ('currency', 'EUR'), ('date', date(2026, 1, 6))])
def test_business_change_and_restore(native_records, field, value):
    obj = native_records[2]
    obj.refresh_from_db()
    original_value = getattr(obj, field)
    original_hash = business_hash(obj)
    setattr(obj, field, value)
    obj.save()
    obj.refresh_from_db()
    assert business_hash(obj) != original_hash
    setattr(obj, field, original_value)
    obj.save()
    obj.refresh_from_db()
    assert business_hash(obj) == original_hash


def test_hash_excludes_exactly_audit_timestamps(native_records):
    for obj in native_records:
        obj.refresh_from_db()
        row = type(obj).objects.values().get(pk=obj.pk)
        del row['created_at'], row['updated_at']
        expected = hashlib.sha256(json.dumps(row, default=str, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert business_hash(obj) == expected
        original = business_hash(obj)
        obj.created_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        obj.updated_at = obj.created_at
        assert business_hash(obj) == original
        for field in row:
            value = getattr(obj, field)
            setattr(obj, field, f'changed:{value}')
            assert business_hash(obj) != original, (type(obj).__name__, field)
            setattr(obj, field, value)


@pytest.mark.django_db(transaction=True)
def test_export_inventory_covers_all_native_models(native_records, tmp_path):
    from django.core.management import call_command
    for obj in native_records:
        obj.refresh_from_db()
    path = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(path), as_of=date(2026, 1, 5))
    result = json.loads(path.read_text())
    assert {(row['kind'], row['record_id'], row['business_hash']) for row in result['business_records']} == {
        (obj._meta.model_name, str(obj.pk), business_hash(obj)) for obj in native_records
    }
