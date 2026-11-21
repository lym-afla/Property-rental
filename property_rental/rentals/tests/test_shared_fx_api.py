from datetime import date
from decimal import Decimal
import json

import pytest
from django.core.management import call_command

from rentals.models import FXAnchor, FXSyncState
from rentals.tests.factories import LeaseRentFactory, TenantFactory, TransactionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def mirror_backend(settings):
    settings.FX_BACKEND = 'mirror'


@pytest.mark.django_db(transaction=True)
def test_tenant_missing_fx_is_typed_and_never_a_complete_total(auth_client, sample_property):
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), payday=5)
    LeaseRentFactory(tenant=tenant, date_rent_set=date(2026, 1, 1), currency='EUR', rent=Decimal('100'))
    TransactionFactory(tenant=tenant, property=sample_property, date=date(2026, 1, 5), category='rent', currency='EUR', amount=Decimal('100'))
    response = auth_client.get(f'/api/v1/analytics/tenants/{tenant.pk}/rent-performance/?start=2026-02-01&end=2026-02-28&grain=month')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'missing_fx'
    assert data['opening_arrears'] is None
    assert 'missing_expected_fx' in data['opening_issues']
    assert 'missing_received_fx' in data['opening_issues']
    point = data['points'][0]
    assert point['expected'] is None
    assert point['variance'] is None
    assert point['cumulative_arrears'] is None


@pytest.mark.django_db(transaction=True)
def test_comparison_attributes_financial_behavior_separately_from_rates(tmp_path, sample_property):
    sample_property.currency = 'USD'
    sample_property.save()
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), lease_end=date(2026, 1, 31), payday=5)
    LeaseRentFactory(tenant=tenant, currency='EUR', date_rent_set=date(2026, 1, 1), rent=Decimal('100'))
    TransactionFactory(property=sample_property, tenant=tenant, currency='EUR', date=date(2026, 1, 5), amount=Decimal('10'), category='rent')
    FXAnchor.objects.create(date=date(2026, 1, 5), currency='USD', value='1', snapshot_id='s')
    FXAnchor.objects.create(date=date(2026, 1, 5), currency='EUR', value='0.5', snapshot_id='s')
    path = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(path))
    data = json.loads(path.read_text())
    catalog = {item['cause']: item for item in data['behavioral_differences']}
    assert {'rent_total_face_value', 'scheduler_rent_denomination', 'native_stats_and_pnl', 'identity_requires_coverage', 'typed_missing_tenant_fx', 'provisional_completed_day'} <= catalog.keys()
    tx = next(r for r in data['records'] if r['kind'] == 'transaction' and r['target_currency'] == 'USD')
    assert tx['multiplier_difference_cause'] == 'reference_coverage'
    assert {'rent_total_face_value', 'native_stats_and_pnl'} <= set(tx['applicable_behavioral_causes'])
    due = next(r for r in data['records'] if r['kind'] == 'lease_due' and r['target_currency'] == 'USD')
    assert 'scheduler_rent_denomination' in due['applicable_behavioral_causes']


@pytest.fixture
def mirror():
    FXSyncState.objects.create(pk=1, release_id='release-old', seq=1, history_epoch=0)
    for day in (4, 5, 6):
        for currency, value in [('USD', '1'), ('EUR', '0.5'), ('RUB', '80')]:
            FXAnchor.objects.create(date=date(2026, 1, day), currency=currency, value=value,
                                    observation_date=None if currency == 'USD' else date(2026, 1, 4), snapshot_id=f'snapshot-{day}')


def test_mirror_range_has_direction_provenance_and_no_network(auth_client, mirror, monkeypatch):
    import requests
    def offline(*args, **kwargs):
        raise AssertionError('table reads must stay local')
    monkeypatch.setattr(requests, 'request', offline)
    response = auth_client.get('/api/v1/fx/?base=EUR&quote=RUB&start=2026-01-04&end=2026-01-06&page_size=2')
    assert response.status_code == 200
    data = response.json()
    assert data['backend'] == 'mirror'
    assert data['release_id'] == 'release-old'
    assert data['count'] == 3
    row = data['results'][0]
    assert row['rate'] == '160.000000000000000000'
    assert row['from_currency'] == 'EUR' and row['to_currency'] == 'RUB'
    assert row['direction'] == 'RUB per EUR'
    assert row['kind'] == 'derived'
    assert row['path'] == ['EUR', 'USD', 'RUB']
    assert row['sources'] == ['CBR', 'ECB']
    assert row['date'] == '2026-01-06'
    assert row['observation_date'] == '2026-01-04'
    assert row['carried_forward'] is True and row['provisional'] is False
    assert row['snapshot_id'] == 'snapshot-6'
    assert row['details_token']
    assert FXAnchor.objects.count() == 9


def test_pagination_retains_old_rows_after_promotion_and_outage(auth_client, mirror):
    data = auth_client.get('/api/v1/fx/?start=2026-01-04&end=2026-01-06&page_size=2').json()
    assert isinstance(data, dict), 'mirror returns a paginated envelope'
    FXAnchor.objects.filter(currency='EUR').update(value='0.8', snapshot_id='corrected')
    FXSyncState.objects.filter(pk=1).update(release_id='release-new', seq=2, history_epoch=1)
    page = auth_client.get(data['next']).json()
    assert page['release_id'] == 'release-old'
    assert page['results'][0]['rate'] == '0.500000000000000000'
    assert page['results'][0]['snapshot_id'] == 'snapshot-4'
    assert page['next'] is None


@pytest.mark.parametrize('params', [
    'start=2026-01-01&end=2026-02-02', 'base=BAD', 'start=nope',
    'page_size=0', 'page_size=32', 'cursor=bad', 'cursor=' + 'x' * 6001,
])
def test_browse_rejects_invalid_or_unbounded_input(auth_client, mirror, params):
    assert auth_client.get('/api/v1/fx/?' + params).status_code == 400


def test_browse_empty_unsynced_and_missing_states(auth_client, mirror):
    missing = auth_client.get('/api/v1/fx/?base=GBP&quote=USD&start=2026-01-04&end=2026-01-04').json()
    assert isinstance(missing, dict)
    assert missing['results'][0]['rate'] is None
    assert missing['results'][0]['error'] == 'unsupported_currency'
    FXAnchor.objects.all().delete()
    assert auth_client.get('/api/v1/fx/').json()['status'] == 'empty'
    FXSyncState.objects.all().delete()
    assert auth_client.get('/api/v1/fx/').json()['status'] == 'unsynced'


def test_details_pin_service_release_and_snapshot_and_fail_clearly(auth_client, mirror, monkeypatch):
    import requests
    def service(method, url, **kwargs):
        assert kwargs['json'] == {'release_id': 'release-old', 'queries': [{'base': 'USD', 'quote': 'EUR', 'date': '2026-01-06'}]}
        class Result:
            def raise_for_status(self):
                pass
            def json(self):
                return {'results': [{'release_id': 'release-old', 'snapshot_id': 'snapshot-6', 'multiplier': '0.500000000000000000', 'error': None, 'path': ['USD', 'EUR'], 'observation_ids': ['observed'], 'sources': {'EUR': ['ECB']}}]}
        return Result()
    monkeypatch.setattr(requests, 'request', service)
    data = auth_client.get('/api/v1/fx/?start=2026-01-06&end=2026-01-06').json()
    assert isinstance(data, dict)
    token = data['results'][0]['details_token']
    FXSyncState.objects.filter(pk=1).update(release_id='new', seq=2)
    response = auth_client.get('/api/v1/fx/details/', {'token': token})
    assert response.status_code == 200
    assert response.json()['result']['observation_ids'] == ['observed']
    def offline(*args, **kwargs):
        raise requests.ConnectionError('down')
    monkeypatch.setattr(requests, 'request', offline)
    unavailable = auth_client.get('/api/v1/fx/details/', {'token': token})
    assert unavailable.status_code == 503
    assert unavailable.json()['code'] == 'fx_details_unavailable'
    assert auth_client.get('/api/v1/fx/').status_code == 200


@pytest.mark.parametrize('method,path', [('post', '/api/v1/fx/'), ('patch', '/api/v1/fx/1/'), ('delete', '/api/v1/fx/1/'), ('post', '/api/v1/fx/import/'), ('post', '/update-fx/'), ('post', '/handling/')])
def test_reference_mutation_and_retired_routes_cannot_write(auth_client, mirror, method, path):
    before = list(FXAnchor.objects.values())
    response = getattr(auth_client, method)(path, data=json.dumps({'rate': '999'}), content_type='application/json')
    assert response.status_code in (404, 405)
    assert list(FXAnchor.objects.values()) == before


def test_legacy_endpoint_keeps_array_and_numeric_detail(auth_client, settings):
    from rentals.tests.factories import FXFactory
    settings.FX_BACKEND = 'legacy'
    fx = FXFactory()
    response = auth_client.get('/api/v1/fx/')
    assert isinstance(response.json(), list)
    assert auth_client.get(f'/api/v1/fx/{fx.pk}/').json()['id'] == fx.pk


def test_cursor_rejects_filter_changes_tampering_and_expiry(auth_client, mirror, monkeypatch):
    import time
    from urllib.parse import urlsplit, parse_qs
    data = auth_client.get('/api/v1/fx/?start=2026-01-04&end=2026-01-06&page_size=1').json()
    assert auth_client.get(data['next'] + '&base=RUB').status_code == 400
    token = parse_qs(urlsplit(data['next']).query)['cursor'][0]
    assert auth_client.get('/api/v1/fx/', {'cursor': token[:-2] + 'xx'}).status_code == 400
    now = time.time()
    monkeypatch.setattr(time, 'time', lambda: now + 86401)
    assert auth_client.get(data['next']).status_code == 400


def test_precise_31_day_cursor_fits_bounded_url_and_preserves_all_rows(auth_client):
    from datetime import timedelta
    from uuid import UUID
    import random
    randomizer = random.Random(7)
    FXSyncState.objects.create(pk=1, release_id=str(UUID(int=17)), seq=1, history_epoch=0)
    for offset in range(31):
        day = date(2026, 1, 1) + timedelta(days=offset)
        snapshot_id = str(UUID(int=randomizer.getrandbits(128)))
        FXAnchor.objects.create(date=day, currency='USD', value='1.000000000000000000', snapshot_id=snapshot_id)
        digits = ''.join(str(randomizer.randrange(10)) for _ in range(18))
        FXAnchor.objects.create(date=day, currency='EUR', value='1234567890123456789.' + digits, snapshot_id=snapshot_id, observation_date=day)
    data = auth_client.get('/api/v1/fx/?start=2026-01-01&end=2026-01-31&page_size=1').json()
    assert len(data['first']) < 6000
    seen = [data['results'][0]['date']]
    while data['next']:
        assert len(data['next']) < 6000
        data = auth_client.get(data['next']).json()
        seen.append(data['results'][0]['date'])
    assert len(seen) == len(set(seen)) == 31
    assert seen[-1] == '2026-01-01'


@pytest.mark.parametrize('field,bad', [('release_id', 'wrong'), ('snapshot_id', 'wrong'), ('multiplier', '999')])
def test_details_reject_wrong_release_snapshot_or_rate(auth_client, mirror, monkeypatch, field, bad):
    from rentals.services.fx_client import FXClient
    data = auth_client.get('/api/v1/fx/?start=2026-01-06&end=2026-01-06').json()
    item = {'release_id': 'release-old', 'snapshot_id': 'snapshot-6', 'multiplier': '0.500000000000000000', 'error': None}
    item[field] = bad
    monkeypatch.setattr(FXClient, 'rates', lambda *args: {'results': [item]})
    assert auth_client.get('/api/v1/fx/details/', {'token': data['results'][0]['details_token']}).status_code == 503


def test_anonymous_reference_reads_are_rejected(client, mirror):
    for path in ['/api/v1/fx/', '/api/v1/fx/details/?token=invalid', '/api/v1/fx/1/']:
        assert client.get(path).status_code in (401, 403)


def test_reference_models_have_no_admin_write_bypass():
    from django.contrib import admin
    from rentals.models import FX
    assert all(model not in admin.site._registry for model in (FX, FXAnchor, FXSyncState))


def test_direct_pair_is_a_read_and_legacy_detail_never_leaks_in_mirror(auth_client, mirror):
    from rentals.tests.factories import FXFactory
    legacy = FXFactory()
    count = FXAnchor.objects.count()
    data = auth_client.get('/api/v1/fx/?base=EUR&quote=USD&start=2026-01-06&end=2026-01-06').json()
    assert data['results'][0]['kind'] == 'direct'
    assert data['results'][0]['rate'] == '2.000000000000000000'
    assert auth_client.get(f'/api/v1/fx/{legacy.pk}/').status_code == 404
    assert FXAnchor.objects.count() == count


@pytest.mark.django_db(transaction=True)
def test_tenant_partial_periods_preserve_valid_rows_but_not_cumulative(auth_client, sample_property):
    sample_property.currency = 'USD'
    sample_property.save()
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), payday=5)
    LeaseRentFactory(tenant=tenant, date_rent_set=date(2026, 1, 1), currency='USD', rent=Decimal('100'))
    for day in (date(2026, 1, 5), date(2026, 3, 5)):
        FXAnchor.objects.create(date=day, currency='USD', value='1', snapshot_id=day.isoformat())
    FXSyncState.objects.create(pk=1, release_id='partial', seq=1, history_epoch=0)
    data = auth_client.get(f'/api/v1/analytics/tenants/{tenant.pk}/rent-performance/?start=2026-01-01&end=2026-03-31&grain=month').json()
    assert data['status'] == 'partial_data'
    january, february, march = data['points']
    assert january['expected'] == 100 and january['cumulative_arrears'] == -100
    assert february['expected'] is None and february['cumulative_arrears'] is None
    assert march['expected'] == 100 and march['variance'] == -100
    assert march['cumulative_arrears'] is None
    assert 'incomplete_cumulative_history' in march['issues']


@pytest.mark.django_db(transaction=True)
def test_comparison_does_not_attribute_decimal_formatting_as_a_rate_change(tmp_path, sample_property):
    from rentals.models import FX
    sample_property.currency = 'USD'
    sample_property.save()
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), lease_end=date(2026, 1, 31))
    TransactionFactory(property=sample_property, tenant=tenant, category='rent', date=date(2026, 1, 5), currency='EUR', amount=Decimal('10'))
    FX.objects.create(date=date(2026, 1, 5), from_currency='EUR', to_currency='USD', rate=Decimal('2'))
    for currency, value in [('USD', '1'), ('EUR', '0.5'), ('GBP', '0.25')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output))
    rows = json.loads(output.read_text())['records']
    usd = next(row for row in rows if row['kind'] == 'transaction' and row['target_currency'] == 'USD')
    assert usd['multiplier_difference_cause'] is None
    assert 'rent_total_face_value' in usd['applicable_behavioral_causes']
    gbp = next(row for row in rows if row['kind'] == 'transaction' and row['target_currency'] == 'GBP')
    assert 'rent_total_face_value' not in gbp['applicable_behavioral_causes']
    assert 'native_stats_and_pnl' not in gbp['applicable_behavioral_causes']


@pytest.mark.django_db(transaction=True)
def test_comparison_names_precision_only_differences(tmp_path, sample_property):
    from rentals.models import FX
    sample_property.currency = 'USD'
    sample_property.save()
    TransactionFactory(property=sample_property, currency='EUR', date=date(2026, 1, 5), amount=Decimal('10'))
    FX.objects.create(date=date(2026, 1, 5), from_currency='USD', to_currency='EUR', rate=Decimal('0.9'))
    for currency, value in [('USD', '1'), ('EUR', '0.9')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output))
    row = next(row for row in json.loads(output.read_text())['records'] if row['target_currency'] == 'USD')
    assert row['multiplier_difference_cause'] == 'decimal_precision'


def test_first_page_link_reconstructs_same_release_after_promotion(auth_client, mirror):
    page = auth_client.get('/api/v1/fx/?start=2026-01-04&end=2026-01-06&page_size=1').json()
    assert page.get('first'), 'the initial page must have an immutable signed link too'
    assert len(page['first']) < 6000
    FXAnchor.objects.filter(currency='EUR').update(value='0.8', snapshot_id='corrected')
    FXSyncState.objects.filter(pk=1).update(release_id='release-new', seq=2, history_epoch=1)
    restored = auth_client.get(page['first']).json()
    assert restored['release_id'] == 'release-old'
    assert restored['results'][0]['date'] == '2026-01-06'
    assert restored['results'][0]['rate'] == '0.500000000000000000'
    assert restored['results'][0]['snapshot_id'] == 'snapshot-6'


@pytest.mark.django_db(transaction=True)
def test_comparison_attributes_unassigned_foreign_rent_in_native_totals(tmp_path, sample_property):
    from django.test import override_settings
    sample_property.currency = 'USD'
    sample_property.save()
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), lease_end=date(2026, 1, 31))
    TransactionFactory(property=sample_property, tenant=None, date=date(2026, 1, 5), currency='EUR', amount=Decimal('10'), category='rent')
    for currency, value in [('USD', '1'), ('EUR', '0.5')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    with override_settings(FX_BACKEND='legacy'):
        assert tenant.rent_total(date(2026, 1, 31)) == Decimal('10')
    assert tenant.rent_total(date(2026, 1, 31)) == Decimal('20')
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output))
    rows = json.loads(output.read_text())['records']
    native = next(row for row in rows if row['kind'] == 'transaction' and row['target_currency'] == 'USD')
    assert 'rent_total_face_value' in native['applicable_behavioral_causes']
    other = next(row for row in rows if row['kind'] == 'transaction' and row['target_currency'] == 'GBP')
    assert 'rent_total_face_value' not in other['applicable_behavioral_causes']


@pytest.mark.django_db(transaction=True)
def test_comparison_attributes_same_currency_effective_rent_ties(tmp_path, sample_property):
    from django.test import override_settings
    sample_property.currency = 'USD'
    sample_property.save()
    tenant = TenantFactory(property=sample_property, lease_start=date(2026, 1, 1), lease_end=date(2026, 1, 31), payday=5)
    LeaseRentFactory(tenant=tenant, currency='USD', date_rent_set=date(2026, 1, 1), rent=Decimal('100'))
    selected = LeaseRentFactory(tenant=tenant, currency='USD', date_rent_set=date(2026, 1, 1), rent=Decimal('200'))
    FXAnchor.objects.create(date=date(2026, 1, 5), currency='USD', value='1', snapshot_id='s')
    with override_settings(FX_BACKEND='legacy'):
        assert tenant.debt(date(2026, 1, 31)) == Decimal('-100')
    assert tenant.debt(date(2026, 1, 31)) == Decimal('-200')
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output))
    data = json.loads(output.read_text())
    assert 'scheduler_rent_selection' in {item['cause'] for item in data['behavioral_differences']}
    rows = [row for row in data['records'] if row['kind'] == 'lease_due' and row['target_currency'] == 'USD']
    assert len(rows) == 1
    assert 'scheduler_rent_selection' in rows[0]['applicable_behavioral_causes']
    assert 'scheduler_rent_denomination' not in rows[0]['applicable_behavioral_causes']
    selected.date_rent_set = date(2026, 1, 2)
    selected.save()
    call_command('export_fx_comparison', output=str(output))
    untied = next(row for row in json.loads(output.read_text())['records'] if row['kind'] == 'lease_due' and row['target_currency'] == 'USD')
    assert 'scheduler_rent_selection' not in untied['applicable_behavioral_causes']
