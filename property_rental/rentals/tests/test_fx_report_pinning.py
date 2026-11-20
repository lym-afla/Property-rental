from rentals.tests.shared_fx_helpers import INITIAL_POLICY_HASH as _POLICY_HASH
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import hashlib
import json

import pytest
from django.db import connections
from django.test import override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from rentals.api.analytics_views import _PortfolioAnalyticsView
from rentals.models import FXAnchor, FXSyncState
from rentals.services.fx import get_rate, PreloadedConverter
from rentals.services.fx_mirror import sync


def seed():
    FXSyncState.objects.create(pk=1, release_id='old', seq=1, history_epoch=1)
    for currency, value in [('USD', '1'), ('EUR', '0.9')]:
        FXAnchor.objects.create(date=date(2026, 1, 6), currency=currency, value=value,
                                observation_date=date(2026, 1, 6) if currency == 'EUR' else None, snapshot_id='old')


class Promotion:
    def current_release(self):
        return {'id': 'new', 'seq': 2, 'predecessor_id': 'old', 'chain_hash': 'a'*64, 'history_epoch': 2,
                'policy_id': 'initial-v1', 'max_fiat_age_days': 14, 'latest_completed_date': '2026-01-06',
                'coverage': {currency: [{'start': '2026-01-06', 'end': '2026-01-06'}] for currency in ['EUR', 'USD']}}
    def changes(self, after_seq):
        canonical = {'date': '2026-01-06', 'policy_id': 'initial-v1', 'policy_hash': _POLICY_HASH,
                     'values': {'EUR': '0.8', 'USD': '1'}, 'observation_ids': [], 'coverage': ['EUR', 'USD'],
                     'observation_dates': {'EUR': '2026-01-06'}, 'statuses': {'EUR': 'completed', 'USD': 'completed'}}
        value = canonical | {'snapshot_id': 'new', 'hash_version': 2, 'sources': {},
                             'content_hash': hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        yield {'release_id': 'new', 'after_seq': after_seq, 'next_cursor': None, 'items': [value]}


def promote_on_separate_connection():
    try:
        state = sync(Promotion())
        assert connections['default'].in_atomic_block is False
        assert FXSyncState.objects.get(pk=1).release_id == 'new'
        return state.seq
    finally:
        connections.close_all()


@pytest.mark.django_db(transaction=True)
@override_settings(FX_BACKEND='mirror')
def test_sync_committed_mid_report_does_not_change_values_or_release(landlord_user):
    seed()
    calls = []
    class View(_PortfolioAnalyticsView):
        def get(self, request):
            calls.append(1)
            before = get_rate('USD', 'EUR', date(2026, 1, 6))['FX']
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(promote_on_separate_connection).result(timeout=10) == 2
            after = get_rate('USD', 'EUR', date(2026, 1, 6))['FX']
            return Response({'before': str(before), 'after': str(after)})
    request = APIRequestFactory().get('/')
    force_authenticate(request, user=landlord_user)
    response = View.as_view()(request)
    assert response.status_code == 200
    assert calls == [1]
    assert response.data['before'] == response.data['after'] == '0.900000000000000000'
    assert response.data['fx']['release_id'] == 'old'
    assert response.data['fx']['history_epoch'] == 1
    assert FXSyncState.objects.get(pk=1).release_id == 'new'
    assert get_rate('USD', 'EUR', date(2026, 1, 6))['FX'] == Decimal('0.8')


@pytest.mark.django_db(transaction=True)
@override_settings(FX_BACKEND='mirror')
def test_preloaded_converter_pins_values_across_a_committed_sync():
    seed()
    converter = PreloadedConverter([], 'EUR')
    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(promote_on_separate_connection).result(timeout=10) == 2
    assert converter.convert(Decimal('10'), 'USD', 'EUR', date(2026, 1, 6)) == Decimal('9')
    assert get_rate('USD', 'EUR', date(2026, 1, 6))['FX'] == Decimal('0.8')


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_mirror_capture_reads_state_and_anchors_in_one_statement(django_assert_num_queries):
    from rentals.services.fx_mirror import capture
    seed()
    with django_assert_num_queries(1):
        capture()


@pytest.mark.django_db(transaction=True)
@override_settings(FX_BACKEND='mirror')
def test_initial_sync_does_not_enter_an_already_captured_empty_report(landlord_user):
    from rentals.services.fx import MissingFXRate
    class View(_PortfolioAnalyticsView):
        def get(self, request):
            with pytest.raises(MissingFXRate):
                get_rate('USD', 'EUR', date(2026, 1, 6))
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(promote_on_separate_connection).result(timeout=10) == 2
            with pytest.raises(MissingFXRate):
                get_rate('USD', 'EUR', date(2026, 1, 6))
            return Response({'empty': True})
    request = APIRequestFactory().get('/')
    force_authenticate(request, user=landlord_user)
    response = View.as_view()(request)
    assert response.status_code == 200
    assert response.data['fx']['release_id'] is None
    assert FXSyncState.objects.get(pk=1).release_id == 'new'


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_standalone_resolution_captures_only_requested_and_latest_pair_anchors(monkeypatch):
    from datetime import timedelta
    from rentals.services import fx_mirror
    first = date(2025, 1, 1)
    FXAnchor.objects.bulk_create([
        FXAnchor(date=first + timedelta(days=offset), currency=currency, value=value, snapshot_id='s')
        for offset in range(100)
        for currency, value in [('USD', '1'), ('EUR', '0.9'), ('RUB', '90')]
    ])
    captured = []
    original = fx_mirror.capture
    def capture(*args, **kwargs):
        selected = original(*args, **kwargs)
        captured.append(selected)
        return selected
    monkeypatch.setattr(fx_mirror, 'capture', capture)
    assert get_rate('USD', 'EUR', first + timedelta(days=10))['FX'] == Decimal('0.9')
    assert len(captured) == 1
    assert set(captured[0].anchors) == {first + timedelta(days=10), first + timedelta(days=99)}
    assert sum(len(anchors) for anchors in captured[0].anchors.values()) == 4


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('entry_point', ['analytics', 'property'])
@override_settings(FX_BACKEND='mirror')
def test_postgresql_report_actually_uses_repeatable_read(landlord_user, entry_point):
    from django.db import connection
    from psycopg import IsolationLevel
    from rentals.api.views import _consistent_fx_report

    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL report isolation contract')
    seed()
    connection.ensure_connection()
    original = connection.connection.isolation_level
    connection.connection.isolation_level = IsolationLevel.READ_COMMITTED
    observed = {}

    def calculate():
        with connection.cursor() as cursor:
            cursor.execute('SHOW transaction_isolation')
            observed['isolation'] = cursor.fetchone()[0]
        observed['before'] = FXAnchor.objects.get(currency='EUR').value
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(promote_on_separate_connection).result(timeout=10) == 2
        observed['after'] = FXAnchor.objects.get(currency='EUR').value
        observed['release'] = FXSyncState.objects.get(pk=1).release_id
        return Response({'ok': True})

    class AnalyticsView(_PortfolioAnalyticsView):
        def get(self, request):
            return calculate()

    class PropertyView:
        @_consistent_fx_report
        def get(self, request):
            return calculate()

    try:
        request = APIRequestFactory().get('/')
        force_authenticate(request, user=landlord_user)
        response = (AnalyticsView.as_view()(request) if entry_point == 'analytics'
                    else PropertyView().get(request))
        assert response.status_code == 200
        assert observed == {'isolation': 'repeatable read', 'before': '0.9',
                            'after': '0.9', 'release': 'old'}
        assert FXSyncState.objects.get(pk=1).release_id == 'new'
        with connection.cursor() as cursor:
            cursor.execute('SHOW transaction_isolation')
            assert cursor.fetchone()[0] == 'read committed'
    finally:
        connection.connection.isolation_level = original


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('isolation', ['READ COMMITTED', 'REPEATABLE READ', 'SERIALIZABLE'])
def test_postgresql_report_checks_existing_transaction_isolation(isolation):
    from django.db import connection, transaction
    from rentals.services.fx_report_transaction import repeatable_read

    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL report isolation contract')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f'SET TRANSACTION ISOLATION LEVEL {isolation}')
            cursor.execute('SELECT 1')
        if isolation == 'READ COMMITTED':
            with pytest.raises(RuntimeError, match='require REPEATABLE READ'):
                with repeatable_read():
                    pytest.fail('A report entered a READ COMMITTED transaction')
        else:
            with repeatable_read(), connection.cursor() as cursor:
                cursor.execute('SHOW transaction_isolation')
                assert cursor.fetchone()[0] == isolation.lower()


@pytest.mark.django_db(transaction=True)
def test_sqlite_report_keeps_existing_transaction_behavior():
    from django.db import connection
    from rentals.services.fx_report_transaction import repeatable_read

    if connection.vendor != 'sqlite':
        pytest.skip('SQLite report transaction contract')
    assert not connection.in_atomic_block
    with repeatable_read():
        assert not connection.in_atomic_block
