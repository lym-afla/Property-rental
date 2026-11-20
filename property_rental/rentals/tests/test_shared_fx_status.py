from rentals.tests.shared_fx_helpers import INITIAL_POLICY_HASH as _POLICY_HASH
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json

import pytest
from django.test import override_settings

from rentals.models import FXAnchor, FXSyncState
from rentals.services.fx import get_rate, MissingFXRate, PreloadedConverter
from rentals.services.fx_mirror import report_provisional, sync

pytestmark = pytest.mark.django_db


def item(status='held', version=2):
    canonical = {'date': '2026-01-06', 'policy_id': 'initial-v1', 'policy_hash': _POLICY_HASH,
                 'values': {'EUR': '0.9', 'USD': '1'}, 'observation_ids': [],
                 'coverage': ['EUR', 'USD'], 'observation_dates': {'EUR': '2026-01-05'}}
    statuses = {'EUR': status, 'USD': 'completed'}
    if version == 2:
        canonical['statuses'] = statuses
    return canonical | {'statuses': statuses, 'hash_version': version, 'snapshot_id': 's', 'sources': {},
                        'content_hash': hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


class Client:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def current_release(self):
        return {'id': 'release', 'seq': 1, 'predecessor_id': None, 'chain_hash': 'a' * 64, 'history_epoch': 1,
                'policy_id': 'initial-v1', 'max_fiat_age_days': 14, 'latest_completed_date': '2026-01-06',
                'coverage': {currency: [{'start': '2026-01-06', 'end': '2026-01-06'}] for currency in ['EUR', 'USD']}}

    def changes(self, after_seq):
        yield {'release_id': 'release', 'after_seq': after_seq, 'next_cursor': None, 'items': [self.snapshot]}


@pytest.mark.parametrize('version,status', [(1, 'carried'), (2, 'held')])
def test_sync_preserves_v1_and_v2_status(version, status):
    sync(Client(item(status, version)))
    assert FXAnchor.objects.get(currency='EUR').status == status
    assert FXAnchor.objects.get(currency='USD').status == 'completed'


@pytest.mark.parametrize('tamper', ['held_to_carried', 'invalid', 'missing', 'extra'])
def test_sync_rejects_invalid_or_unhashed_status(tamper):
    snapshot = item()
    if tamper == 'held_to_carried': snapshot['statuses']['EUR'] = 'carried'
    if tamper == 'invalid': snapshot['statuses']['EUR'] = 'unknown'
    if tamper == 'missing': del snapshot['statuses']['EUR']
    if tamper == 'extra': snapshot['statuses']['RUB'] = 'completed'
    with pytest.raises(ValueError):
        sync(Client(snapshot))
    assert not FXAnchor.objects.exists()
    assert not FXSyncState.objects.exists()


@override_settings(FX_BACKEND='mirror')
def test_held_conversion_is_provisional_and_excluded_from_caches(auth_client, monkeypatch):
    from django.core.cache import cache
    def reject_cache(*args, **kwargs):
        raise AssertionError('held conversions cannot enter persisted caches')
    monkeypatch.setattr(cache, 'set', reject_cache)
    FXSyncState.objects.create(pk=1, release_id='release', seq=1, history_epoch=1)
    for currency, value, status in [('USD', '1', 'completed'), ('EUR', '0.9', 'held')]:
        FXAnchor.objects.create(date=date(2026, 1, 6), currency=currency, value=value, status=status,
                                observation_date=date(2026, 1, 5) if currency == 'EUR' else None, snapshot_id='s')
    touched = set()
    token = report_provisional.set(touched)
    try:
        result = get_rate('EUR', 'USD', date(2026, 1, 6))
    finally:
        report_provisional.reset(token)
    assert result['FX'] == Decimal('1.111111111111111111')
    assert result['provisional'] is True and result['cacheable'] is False
    assert result['effective_date'] == date(2026, 1, 6)
    assert result['source_date'] == date(2026, 1, 5)
    assert result['statuses'] == {'EUR': 'held', 'USD': 'completed'}
    assert touched == {'2026-01-06'}
    assert PreloadedConverter([], 'USD').convert(Decimal('1'), 'EUR', 'USD', date(2026, 1, 6)) == result['FX']
    row = auth_client.get('/api/v1/fx/?base=EUR&quote=USD&start=2026-01-06&end=2026-01-06').json()['results'][0]
    assert row['status'] == 'held' and row['statuses']['EUR'] == 'held'
    assert row['provisional'] is True and row['source_date'] == '2026-01-05'


@override_settings(FX_BACKEND='mirror')
@pytest.mark.parametrize('age,available', [(14, True), (15, False)])
def test_held_ceiling_measures_oldest_path_observation(age, available):
    day = date(2026, 1, 20)
    FXAnchor.objects.create(date=day, currency='USD', value='1', snapshot_id='s', status='completed')
    FXAnchor.objects.create(date=day, currency='CNY', value='7', observation_date=day-timedelta(days=age), snapshot_id='s', status='held')
    if available:
        assert get_rate('USD', 'CNY', day)['provisional'] is True
    else:
        with pytest.raises(MissingFXRate) as failure:
            get_rate('USD', 'CNY', day)
        assert failure.value.code == 'stale'


def test_v1_hash_cannot_claim_an_unhashed_hold():
    with pytest.raises(ValueError):
        sync(Client(item('held', 1)))
    assert not FXAnchor.objects.exists()


def test_status_only_release_changes_are_synced_without_epoch_change():
    class Promotion(Client):
        seq = 1
        def current_release(self):
            return super().current_release() | {'id': f'release-{self.seq}', 'seq': self.seq}
        def changes(self, after_seq):
            value = item('held' if self.seq == 1 else 'carried')
            value['snapshot_id'] = f'snapshot-{self.seq}'
            yield {'release_id': f'release-{self.seq}', 'after_seq': after_seq, 'next_cursor': None, 'items': [value]}

    client = Promotion(None)
    sync(client)
    assert FXAnchor.objects.get(currency='EUR').status == 'held'
    client.seq = 2
    sync(client)
    assert FXAnchor.objects.get(currency='EUR').status == 'carried'
    assert FXSyncState.objects.get(pk=1).history_epoch == 1
    incremental = list(FXAnchor.objects.order_by('date', 'currency').values_list('date', 'currency', 'value', 'status', 'observation_date', 'snapshot_id'))
    FXAnchor.objects.all().delete()
    FXSyncState.objects.all().delete()
    sync(client)
    assert list(FXAnchor.objects.order_by('date', 'currency').values_list('date', 'currency', 'value', 'status', 'observation_date', 'snapshot_id')) == incremental


@pytest.mark.django_db(transaction=True)
def test_status_migration_retains_existing_anchor_values_and_infers_carry():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    executor = MigrationExecutor(connection)
    previous = [('rentals', '0029_fxanchor_fxsyncstate_and_more')]
    current = [('rentals', '0030_fxanchor_status')]
    executor.migrate(previous)
    try:
        old = executor.loader.project_state(previous).apps.get_model('rentals', 'FXAnchor')
        old.objects.bulk_create([
            old(date=date(2026, 1, 6), currency='USD', value='1', snapshot_id='s'),
            old(date=date(2026, 1, 6), currency='EUR', value='0.9', observation_date=date(2026, 1, 5), snapshot_id='s'),
            old(date=date(2026, 1, 6), currency='RUB', value='90', observation_date=date(2026, 1, 6), snapshot_id='s'),
        ])
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(current)
    assert list(FXAnchor.objects.order_by('currency').values_list('currency', 'value', 'status')) == [
        ('EUR', '0.9', 'carried'), ('RUB', '90', 'completed'), ('USD', '1', 'completed')]
