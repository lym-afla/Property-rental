from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(FX_BACKEND="mirror")
def test_mirror_resolvers_use_anchor_ratios_without_network():
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx import get_rate, PreloadedConverter

    FXSyncState.objects.create(pk=1, release_id="release-1", seq=1, history_epoch=1)
    for currency, value in [("USD", "1"), ("EUR", "0.9"), ("RUB", "90")]:
        FXAnchor.objects.create(date=date(2026, 11, 5), currency=currency, value=value, snapshot_id="snapshot-1", observation_date=date(2026, 11, 5))
    assert get_rate("EUR", "RUB", date(2026, 11, 5))["FX"] == Decimal("100.000000000000000000")
    assert PreloadedConverter([], "RUB").convert(Decimal("2"), "EUR", "RUB", date(2026, 11, 5)) == Decimal("200.000000000000000000")


@pytest.mark.django_db
def test_sync_rejects_bad_hash_without_changing_existing_release():
    from rentals.models import FXSyncState
    from rentals.services.fx_mirror import sync

    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)

    class Client:
        def current_release(self):
            return _review_release(history_epoch=1, latest_completed_date='2026-11-05', coverage={'USD': [{'start': '2026-11-05', 'end': '2026-11-05'}]})

        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [{'date': '2026-11-05', 'policy_id': 'initial-v1', 'policy_hash': _POLICY_HASH, 'values': {'USD': '1'}, 'observation_ids': [], 'coverage': ['USD'], 'observation_dates': {}, 'snapshot_id': 's', 'content_hash': 'bad', 'sources': {}}]}

    with pytest.raises(ValueError):
        sync(Client())
    assert FXSyncState.objects.get(pk=1).release_id == 'old'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_identity_requires_covered_anchor():
    from rentals.models import FXAnchor
    from rentals.services.fx import get_rate, MissingFXRate

    FXAnchor.objects.create(date=date(2026, 1, 1), currency='USD', value='1', snapshot_id='s')
    with pytest.raises(MissingFXRate):
        get_rate('EUR', 'EUR', date(2026, 1, 1))


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_provisional_rejects_observation_newer_than_snapshot():
    from rentals.models import FXAnchor
    from rentals.services.fx import get_rate, MissingFXRate

    for currency, value, observed in [('USD', '1', None), ('EUR', '0.9', date(2026, 1, 2))]:
        FXAnchor.objects.create(date=date(2026, 1, 1), currency=currency, value=value, snapshot_id='s', observation_date=observed)
    with pytest.raises(MissingFXRate):
        get_rate('USD', 'EUR', date(2026, 1, 3))


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_report_retains_captured_release_when_database_state_changes(landlord_user):
    from rest_framework.response import Response
    from rest_framework.test import APIRequestFactory, force_authenticate
    from rentals.api.analytics_views import _PortfolioAnalyticsView
    from rentals.models import FXSyncState

    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    calls = []

    class View(_PortfolioAnalyticsView):
        def get(self, request):
            calls.append(1)
            if len(calls) == 1:
                FXSyncState.objects.filter(pk=1).update(release_id='new', seq=2)
            return Response({'calculation': len(calls)})

    request = APIRequestFactory().get('/')
    force_authenticate(request, user=landlord_user)
    response = View.as_view()(request)
    assert response.data['calculation'] == 1
    assert response.data['fx']['release_id'] == 'old'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_tenant_missing_conversion_is_not_silently_skipped():
    from rentals.analytics.tenant import _converted
    from rentals.services.fx import PreloadedConverter

    assert _converted(PreloadedConverter([], 'USD'), Decimal('10'), 'EUR', 'USD', date(2026, 1, 1)) == (None, 'missing_fx')


@pytest.mark.django_db
def test_sync_applies_complete_pages_and_is_idempotent():
    import hashlib
    import json
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx_mirror import sync

    canonical = {'date': '2026-11-05', 'policy_id': 'initial-v1', 'policy_hash': _POLICY_HASH, 'values': {'EUR': '0.9', 'USD': '1'}, 'observation_ids': [], 'coverage': ['EUR', 'USD'], 'observation_dates': {'EUR': '2026-11-05'}}
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    item = {**canonical, 'snapshot_id': 's', 'content_hash': digest, 'sources': {}}

    class Client:
        def current_release(self):
            return _review_release(id='release', seq=1, history_epoch=1, latest_completed_date='2026-11-05', coverage={currency: [{'start': '2026-11-05', 'end': '2026-11-05'}] for currency in ('EUR', 'USD')})

        def changes(self, after_seq):
            yield {'release_id': 'release', 'after_seq': after_seq, 'next_cursor': 'cursor', 'items': [item]}
            yield {'release_id': 'release', 'after_seq': after_seq, 'next_cursor': None, 'items': []}

    sync(Client())
    sync(Client())
    assert FXSyncState.objects.get(pk=1).seq == 1
    assert list(FXAnchor.objects.order_by('currency').values_list('currency', 'value')) == [('EUR', '0.9'), ('USD', '1')]


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_tenant_rent_total_converts_mixed_native_currencies():
    from rentals.models import FXAnchor
    from rentals.tests.factories import TenantFactory, TransactionFactory

    tenant = TenantFactory(lease_start=date(2026, 1, 1), property__currency='USD')
    TransactionFactory(property=tenant.property, tenant=tenant, category='rent', currency='EUR', date=date(2026, 1, 5), amount=Decimal('10'))
    for currency, value in [('USD', '1'), ('EUR', '0.5')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    assert tenant.rent_total(date(2026, 1, 31), target_currency='USD') == Decimal('20')


def test_vendored_golden_fixture_hashes():
    import hashlib
    from pathlib import Path
    directory = Path(__file__).parent / 'fixtures' / 'shared_fx'
    assert hashlib.sha256((directory / 'golden-rates.json').read_bytes()).hexdigest() == '4a173c32a06eaa10ce4c9072d47438b1d98a60413f5fc2140dbf2ae5962c9445'
    assert hashlib.sha256((directory / 'golden-api.json').read_bytes()).hexdigest() == '8399120d9d214fad21d11438296b22870c5b43be7afce5bfd480bd065d99938f'
    assert hashlib.sha256((directory / 'boundary-anchors.json').read_bytes()).hexdigest() == '3eb8a234ae378771eae3ae85071e06d0367020f5d21d5e83b9f98cb6e39a7fef'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_completed_golden_rates_match_both_resolvers():
    import json
    from pathlib import Path
    from rentals.models import FXAnchor
    from rentals.services.fx import get_rate, PreloadedConverter

    cases = json.loads((Path(__file__).parent / 'fixtures/shared_fx/golden-rates.json').read_text())['cases']
    cases = [case for case in cases if case.get('multiplier') and case['requested_date'] == case['latest_completed_date']]
    for case in cases:
        FXAnchor.objects.all().delete()
        for currency, value in case['anchor_values'].items():
            FXAnchor.objects.create(date=case['requested_date'], currency=currency, value=value, observation_date=case['observation_dates'].get(currency), snapshot_id='golden', status=case.get('statuses', {}).get(currency, 'completed'))
        target_date = date.fromisoformat(case['requested_date'])
        expected = Decimal(case['multiplier'])
        assert get_rate(case['base'], case['quote'], target_date)['FX'] == expected, case['name']
        assert PreloadedConverter([], case['quote']).convert(Decimal(1), case['base'], case['quote'], target_date) == expected, case['name']


@pytest.mark.django_db(transaction=True)
@override_settings(FX_BACKEND='mirror')
def test_comparison_export_covers_native_transaction_without_writing_it(tmp_path):
    import json
    from django.core.management import call_command
    from rentals.models import FXAnchor
    from rentals.tests.factories import TransactionFactory

    row = TransactionFactory(currency='EUR', date=date(2026, 1, 5), amount=Decimal('10'))
    for currency, value in [('USD', '1'), ('EUR', '0.5')]:
        FXAnchor.objects.create(date=row.date, currency=currency, value=value, snapshot_id='s')
    path = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(path))
    result = json.loads(path.read_text())
    entry = next(item for item in result['records'] if item['kind'] == 'transaction' and item['target_currency'] == 'USD')
    assert entry['mirror_multiplier'] == '2.000000000000000000'
    assert len(entry['business_hash']) == 64
    row.refresh_from_db()
    assert row.amount == Decimal('10') and row.currency == 'EUR'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_property_statistics_retain_captured_release(auth_client, sample_property, monkeypatch):
    from rentals.models import FXSyncState
    from rentals.services import financials

    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    calls = []
    def aggregate(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            FXSyncState.objects.filter(pk=1).update(release_id='new', seq=2)
        return Decimal('1')
    monkeypatch.setattr(financials, 'aggregate', aggregate)
    response = auth_client.get('/api/v1/properties/with_stats/?as_of=2026-01-05&currency=EUR')
    assert response.status_code == 200
    assert len(calls) == 4
    assert response['X-FX-Release-ID'] == 'old'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_golden_api_rates_using_independently_observed_anchors():
    import json
    from pathlib import Path
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx import get_rate, PreloadedConverter

    folder = Path(__file__).parent / 'fixtures/shared_fx'
    from rentals.tests.shared_fx_helpers import seed_anchors
    anchors = json.loads((folder / 'boundary-anchors.json').read_text())['dates']
    for anchor_date, snapshot in anchors.items():
        seed_anchors(anchor_date, snapshot['values'], snapshot['observation_dates'], 'boundary')
    FXSyncState.objects.create(pk=1, release_id='boundary', seq=1, history_epoch=1,
                               coverage={currency: [{'start': '2008-01-01', 'end': '2008-01-01'}]
                                         for currency in ['USD','RUB','EUR','GBP','CHF','PLN','CNY','USDT','USDC']})
    for case in json.loads((folder / 'golden-api.json').read_text())['cases']:
        query = case['query']
        as_of = date.fromisoformat(query['date'])
        if case.get('error'):
            from rentals.services.fx import MissingFXRate
            with pytest.raises(MissingFXRate) as failure:
                get_rate(query['base'], query['quote'], as_of)
            assert failure.value.code == case['error']
            with pytest.raises(MissingFXRate) as preloaded_failure:
                PreloadedConverter([], query['quote']).convert(Decimal('1'), query['base'], query['quote'], as_of)
            assert preloaded_failure.value.code == case['error']
        else:
            expected = Decimal(case['multiplier'])
            assert get_rate(query['base'], query['quote'], as_of)['FX'] == expected
            assert PreloadedConverter([], query['quote']).convert(Decimal('1'), query['base'], query['quote'], as_of) == expected


@pytest.mark.django_db
def test_sync_rejects_truncated_page_even_when_cursor_is_removed():
    from rentals.models import FXSyncState
    from rentals.services.fx_mirror import sync

    class Client:
        def current_release(self):
            return _review_release(seq=1, history_epoch=1, latest_completed_date='2026-01-01', coverage={'USD': [{'start': '2026-01-01', 'end': '2026-01-01'}]})
        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': []}

    with pytest.raises(ValueError):
        sync(Client())
    assert not FXSyncState.objects.exists()


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_all_golden_rate_outcomes(monkeypatch):
    import json
    from datetime import datetime
    from pathlib import Path
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services import fx_mirror
    from rentals.services.fx import get_rate, MissingFXRate

    cases = json.loads((Path(__file__).parent / 'fixtures/shared_fx/golden-rates.json').read_text())['cases']
    for case in cases:
        FXAnchor.objects.all().delete()
        FXSyncState.objects.update_or_create(pk=1, defaults={'release_id': 'golden', 'seq': 1, 'history_epoch': 1,
                                                          'coverage': case.get('release_coverage', {}), 'max_fiat_age_days': 14})
        today = date.fromisoformat(case['business_today'])
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls.combine(today, datetime.min.time(), tzinfo=tz)
        monkeypatch.setattr(fx_mirror, 'datetime', Clock)
        requested = date.fromisoformat(case['requested_date'])
        latest = date.fromisoformat(case['latest_completed_date'])
        FXAnchor.objects.create(date=latest, currency='TEST', value='1', snapshot_id='latest')
        for day in {latest, min(requested, latest)}:
            for currency, value in case['anchor_values'].items():
                FXAnchor.objects.create(date=day, currency=currency, value=value, observation_date=case['observation_dates'].get(currency), snapshot_id='golden', status=case.get('statuses', {}).get(currency, 'completed'))
        if case.get('error'):
            from rentals.services.fx import PreloadedConverter
            with pytest.raises(MissingFXRate) as failure:
                get_rate(case['base'], case['quote'], requested)
            assert failure.value.code == case['error'], case['name']
            with pytest.raises(MissingFXRate) as preloaded_failure:
                PreloadedConverter([], case['quote']).convert(Decimal(1), case['base'], case['quote'], requested)
            assert preloaded_failure.value.code == case['error'], case['name']
        else:
            from rentals.services.fx import PreloadedConverter
            result = get_rate(case['base'], case['quote'], requested)
            assert PreloadedConverter([], case['quote']).convert(Decimal(1), case['base'], case['quote'], requested) == Decimal(case['multiplier']), case['name']
            assert result['FX'] == Decimal(case['multiplier']), case['name']
            assert result['effective_date'].isoformat() == case['effective_date'], case['name']
            assert result['provisional'] == case['provisional'], case['name']
            assert result['cacheable'] == case['cacheable'], case['name']


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_property_native_report_rejects_unconvertible_foreign_row(auth_client, sample_property):
    from rentals.tests.factories import TransactionFactory
    TransactionFactory(property=sample_property, category='rent', currency='EUR', amount=Decimal('10'), date=date(2026, 1, 5))
    response = auth_client.get('/api/v1/properties/with_stats/?as_of=2026-01-31')
    assert response.status_code == 422
    assert response.json()['code'] == 'missing_fx'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_debt_requires_conversion_for_foreign_lease_rate():
    from rentals.services.fx import MissingFXRate
    from rentals.tests.factories import LeaseRentFactory, TenantFactory
    tenant = TenantFactory(lease_start=date(2026, 1, 1), payday=5, property__currency='USD')
    LeaseRentFactory(tenant=tenant, date_rent_set=date(2026, 1, 1), currency='EUR', rent=Decimal('100'))
    with pytest.raises(MissingFXRate):
        tenant.debt(date(2026, 1, 31))


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_legacy_pnl_native_mode_does_not_sum_foreign_currency():
    from rentals.services.financials import pnl_calc
    from rentals.services.fx import MissingFXRate
    from rentals.tests.factories import PropertyFactory, TransactionFactory
    prop = PropertyFactory(currency='USD')
    TransactionFactory(property=prop, currency='EUR', amount=Decimal('10'), category='rent', date=date(2026, 1, 5))
    with pytest.raises(MissingFXRate):
        pnl_calc([prop], 'USD', False, 2, as_of=date(2026, 1, 31))


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('backend', ['legacy', 'mirror'])
def test_native_save_and_sqlite_import_do_not_use_network(tmp_path, monkeypatch, settings, backend):
    from django.core.management import call_command
    import requests
    from rentals.management.commands.export_fx_comparison import business_hash
    from rentals.models import FX, FXAnchor, Transaction
    from rentals.tests.factories import PropertyFactory, TransactionFactory
    from rentals.tests.test_migration_command import _clear_destination_rows, _write_source_sqlite

    settings.FX_BACKEND = backend
    def offline(*args, **kwargs):
        raise AssertionError('network access during native write')
    monkeypatch.setattr(requests.sessions.Session, 'request', offline)
    prop = PropertyFactory(id=41)
    row = TransactionFactory(id=73, property=prop, tenant=None, category='rent', period='2026-01', currency='EUR', amount=Decimal('10.00'), date=date(2026, 1, 5), comment='fixed')
    FX.objects.create(date=date(2026, 1, 5), from_currency='EUR', to_currency='USD', rate=Decimal('2'))
    row.refresh_from_db()
    original_hash = business_hash(row)
    assert original_hash == 'babf126e752f3cedc21c4658b2bf51ebd73b14a9de7ddc6235745a9f469f5907'
    source = tmp_path / 'source.sqlite3'
    _write_source_sqlite(source)
    _clear_destination_rows()
    call_command('import_sqlite', source=str(source))
    assert business_hash(Transaction.objects.get(pk=row.pk)) == original_hash
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output))
    import json
    assert any(record['kind'] == 'transaction' and record['business_hash'] == original_hash for record in json.loads(output.read_text())['records'])
    assert business_hash(Transaction.objects.get(pk=row.pk)) == 'babf126e752f3cedc21c4658b2bf51ebd73b14a9de7ddc6235745a9f469f5907'
    assert FXAnchor.objects.count() == 0
    assert FX.objects.count() == (1 if backend == 'legacy' else 0)


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_deposit_only_date_uses_mirror_for_cash_flow(landlord_user):
    from rentals.analytics.cash_flow import portfolio_cash_flow
    from rentals.analytics.filters import AnalyticsFilters, Grain
    from rentals.models import DepositMovement, FXAnchor
    from rentals.tests.factories import TenantFactory

    tenant = TenantFactory(property__owned_by=landlord_user.landlord, property__currency='USD')
    DepositMovement.objects.create(tenant=tenant, date=date(2026, 1, 5), kind='received', currency='EUR', amount=Decimal('10'))
    for currency, value in [('USD', '1'), ('EUR', '0.5')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    filters = AnalyticsFilters(start=date(2026, 1, 1), end=date(2026, 1, 31), grain=Grain.MONTH, currency='USD', comparison=None, property_ids=())
    assert portfolio_cash_flow(landlord_user, filters).points[0]['deposits'] == 20.0


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_mirror_conversion_ignores_hostile_decimal_context():
    from decimal import Inexact, ROUND_DOWN, getcontext, localcontext
    from rentals.models import FXAnchor
    from rentals.services.fx import convert, PreloadedConverter
    for currency, value in [('USD', '1'), ('EUR', '0.9')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, snapshot_id='s')
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        expected = Decimal('1.111111111111111111')
        assert convert(Decimal('1'), 'EUR', 'USD', date(2026, 1, 5)) == expected
        assert PreloadedConverter([], 'USD').convert(Decimal('1'), 'EUR', 'USD', date(2026, 1, 5)) == expected
        assert getcontext().prec == 6 and getcontext().traps[Inexact]


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_provisional_analytics_response_is_not_http_cacheable(landlord_user):
    from rest_framework.response import Response
    from rest_framework.test import APIRequestFactory, force_authenticate
    from rentals.api.analytics_views import _PortfolioAnalyticsView
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx import get_rate
    from django.utils import timezone

    today = timezone.localdate()
    from datetime import timedelta
    for currency, value in [('USD', '1'), ('EUR', '0.9')]:
        FXAnchor.objects.create(date=today - timedelta(days=1), currency=currency, value=value, observation_date=today - timedelta(days=1), snapshot_id='s')
    FXSyncState.objects.create(pk=1, release_id='s', seq=1, history_epoch=1)
    class View(_PortfolioAnalyticsView):
        def get(self, request):
            get_rate('USD', 'EUR', today)
            return Response({'total': 1})
    request = APIRequestFactory().get('/')
    force_authenticate(request, user=landlord_user)
    response = View.as_view()(request)
    assert response.data['fx']['provisional'] is True
    assert 'no-store' in response['Cache-Control']


@pytest.mark.django_db
@pytest.mark.parametrize('backend', ['legacy', 'mirror'])
def test_characterized_rates_and_transaction_aggregate_across_backends(settings, backend):
    from types import SimpleNamespace
    from rentals.models import FX, FXAnchor
    from rentals.services.financials import convert_transactions
    from rentals.services.fx import get_rate, PreloadedConverter
    from rentals.tests.factories import TransactionFactory

    settings.FX_BACKEND = backend
    as_of = date(2026, 1, 5)
    FX.objects.create(date=as_of, from_currency='EUR', to_currency='USD', rate=Decimal('1.25'))
    FX.objects.create(date=as_of, from_currency='USD', to_currency='RUB', rate=Decimal('80'))
    for currency, value in [('USD', '1'), ('EUR', '0.8'), ('RUB', '80')]:
        FXAnchor.objects.create(date=as_of, currency=currency, value=value, snapshot_id='s')
    row = TransactionFactory(date=as_of, currency='EUR', amount=Decimal('2'))
    for source, target, expected in [('EUR', 'USD', Decimal('1.25')), ('USD', 'EUR', Decimal('0.8')), ('EUR', 'RUB', Decimal('100'))]:
        assert get_rate(source, target, as_of)['FX'] == expected
        assert PreloadedConverter([SimpleNamespace(date=as_of, currency=source)], target).convert(Decimal(1), source, target, as_of) == expected
    assert convert_transactions([row], 'RUB', as_of) == Decimal('200')


@pytest.mark.django_db(transaction=True)
def test_comparison_export_rejects_release_write_inside_calculation(tmp_path, monkeypatch):
    import json
    from django.core.management import call_command
    from rentals.management.commands import export_fx_comparison
    from rentals.models import FXAnchor, FXSyncState
    from rentals.tests.factories import TransactionFactory

    row = TransactionFactory(currency='USD', amount=Decimal('10'), date=date(2026, 1, 5))
    FXAnchor.objects.create(date=row.date, currency='USD', value='1', snapshot_id='s')
    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    real_hash = export_fx_comparison.business_hash
    calls = []
    def changing_hash(obj):
        calls.append(1)
        if len(calls) == 1:
            FXSyncState.objects.filter(pk=1).update(release_id='new', seq=2)
        return real_hash(obj)
    monkeypatch.setattr(export_fx_comparison, 'business_hash', changing_hash)
    path = tmp_path / 'comparison.json'
    from django.core.management.base import CommandError
    with pytest.raises(CommandError, match='comparison_write_forbidden'):
        call_command('export_fx_comparison', output=str(path))
    assert FXSyncState.objects.get(pk=1).release_id == 'old'
    assert not path.exists()


_POLICY_HASH = 'dcec25ddeff179e638416303494a030795f7d99883a646634894d1867c2e3aae'


def _review_item(value='0.9', snapshot='old', policy='initial-v1', policy_hash=_POLICY_HASH):
    import hashlib
    import json
    canonical = {'date': '2026-01-05', 'policy_id': policy, 'policy_hash': policy_hash,
                 'values': {'EUR': value, 'USD': '1'}, 'observation_ids': [],
                 'coverage': ['EUR', 'USD'], 'observation_dates': {'EUR': '2026-01-05'}}
    return {**canonical, 'snapshot_id': snapshot, 'sources': {}, 'content_hash': hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()}


def _review_release(**overrides):
    value = {'id': 'new', 'seq': 2, 'predecessor_id': 'old', 'chain_hash': 'a' * 64, 'history_epoch': 2, 'policy_id': 'initial-v1', 'max_fiat_age_days': 14,
             'latest_completed_date': '2026-01-05', 'coverage': {currency: [{'start': '2026-01-05', 'end': '2026-01-05'}] for currency in ['EUR', 'USD']}}
    value.update(overrides)
    return value


@pytest.mark.django_db
def test_sync_omitted_correction_rolls_back_state_and_anchors():
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx_mirror import sync
    state = FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    for currency, value in [('EUR', '0.9'), ('USD', '1')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, observation_date=date(2026, 1, 5) if currency == 'EUR' else None, snapshot_id='old')
    timestamp = state.synced_at
    class Client:
        def current_release(self): return _review_release()
        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [] if after_seq else [_review_item('0.8', 'corrected')]}
    with pytest.raises(ValueError): sync(Client())
    state.refresh_from_db()
    assert (state.release_id, state.seq, state.history_epoch, state.synced_at) == ('old', 1, 1, timestamp)
    assert FXAnchor.objects.get(currency='EUR').value == '0.9'
    assert FXAnchor.objects.get(currency='EUR').snapshot_id == 'old'


@pytest.mark.django_db
@pytest.mark.parametrize('bad_release,bad_item', [
    ({'max_fiat_age_days': -1}, {}), ({'max_fiat_age_days': True}, {}),
    ({'coverage': None}, {}), ({'latest_completed_date': None}, {}),
])
def test_sync_rejects_invalid_ceiling_hash_and_incomplete_metadata(bad_release, bad_item):
    from rentals.models import FXSyncState
    from rentals.services.fx_mirror import sync
    state = FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    timestamp = state.synced_at
    class Client:
        def current_release(self): return _review_release(**bad_release)
        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [_review_item(**bad_item)]}
    with pytest.raises(ValueError): sync(Client())
    state.refresh_from_db()
    assert (state.release_id, state.seq, state.history_epoch, state.synced_at) == ('old', 1, 1, timestamp)


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror', ROOT_URLCONF=__name__)
def test_report_state_change_keeps_single_captured_release(client, landlord_user, monkeypatch):
    import sys
    from django.urls import path
    from rest_framework.response import Response
    from rentals.api.analytics_views import _PortfolioAnalyticsView
    from rentals.models import FXSyncState
    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    class View(_PortfolioAnalyticsView):
        def get(self, request):
            state = FXSyncState.objects.get(pk=1)
            state.seq += 1
            state.save()
            return Response({'ok': True})
    monkeypatch.setattr(sys.modules[__name__], 'urlpatterns', [path('probe/', View.as_view())], raising=False)
    client.force_login(landlord_user)
    response = client.get('/probe/')
    assert response.status_code == 200
    assert response.json()['fx']['release_id'] == 'old'


@pytest.mark.django_db
@pytest.mark.parametrize('omitted', ['coverage', 'latest_completed_date', 'policy_id', 'max_fiat_age_days', 'chain_hash', 'predecessor_id'])
def test_sync_rejects_absent_required_release_metadata(omitted):
    from rentals.models import FXSyncState
    from rentals.services.fx_mirror import sync
    class Client:
        def current_release(self):
            release = _review_release()
            del release[omitted]
            return release
        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [_review_item()]}
    with pytest.raises(ValueError): sync(Client())
    assert not FXSyncState.objects.exists()


@pytest.mark.django_db
def test_correction_audit_accepts_identical_complete_full_feed():
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx_mirror import sync
    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    for currency, value in [('EUR', '0.9'), ('USD', '1')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, observation_date=date(2026, 1, 5) if currency == 'EUR' else None, snapshot_id='old')
    seen = []
    class Client:
        def current_release(self): return _review_release()
        def changes(self, after_seq):
            seen.append(after_seq)
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [_review_item('0.8', 'corrected')]}
    sync(Client())
    assert seen == [1, 0]
    assert FXAnchor.objects.get(currency='EUR').value == '0.8'
    assert FXSyncState.objects.get(pk=1).history_epoch == 2


@pytest.mark.django_db
def test_append_does_not_request_full_correction_audit():
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx_mirror import sync
    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    seen = []
    class Client:
        def current_release(self): return _review_release(history_epoch=1)
        def changes(self, after_seq):
            seen.append(after_seq)
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [_review_item()]}
    sync(Client())
    assert seen == [1]
    assert FXAnchor.objects.count() == 2


@pytest.mark.django_db
def test_correction_audit_does_not_use_staged_rows_to_mask_missing_audit_data():
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx_mirror import sync
    state = FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    for currency, value in [('EUR', '0.9'), ('USD', '1')]:
        FXAnchor.objects.create(date=date(2026, 1, 5), currency=currency, value=value, observation_date=date(2026, 1, 5) if currency == 'EUR' else None, snapshot_id='old')
    timestamp = state.synced_at
    class Client:
        def current_release(self): return _review_release()
        def changes(self, after_seq):
            yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [_review_item('0.8', 'corrected')] if after_seq else []}
    with pytest.raises(ValueError): sync(Client())
    state.refresh_from_db()
    assert (state.release_id, state.seq, state.history_epoch, state.synced_at) == ('old', 1, 1, timestamp)
    assert FXAnchor.objects.get(currency='EUR').value == '0.9'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
@pytest.mark.parametrize('currency', ['USD', 'RUB', 'EUR', 'GBP', 'CHF', 'PLN', 'CNY', 'USDT', 'USDC'])
def test_all_mirror_currencies_start_coverage_in_2008(currency):
    from rentals.models import FXAnchor, FXSyncState
    from rentals.services.fx import get_rate, MissingFXRate
    FXSyncState.objects.create(pk=1, release_id='first', seq=1, history_epoch=1,
                               coverage={currency: [{'start': '2008-01-01', 'end': '2008-01-01'}]})
    FXAnchor.objects.create(date=date(2008, 1, 1), currency='TEST', value='1', snapshot_id='latest')
    with pytest.raises(MissingFXRate) as error:
        get_rate(currency, currency, date(2007, 12, 31))
    assert error.value.code == 'before_coverage'
    FXAnchor.objects.create(date=date(2008, 1, 1), currency=currency, value='1', snapshot_id='first')
    assert get_rate(currency, currency, date(2008, 1, 1))['FX'] == Decimal('1')
