from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from rentals.services import shared_fx_resolver as resolver

COVERAGE = {currency: [{'start': day, 'end': day} for day in ('2026-01-06', '2026-01-08')]
            for currency in ('CAD', 'USD')}


def client():
    class Client:
        def current_release(self):
            return {'id': 'cad-release', 'seq': 1, 'history_epoch': 1, 'predecessor_id': None,
                    'chain_hash': 'a' * 64, 'policy_id': 'new-currency-policy', 'max_fiat_age_days': 14,
                    'latest_completed_date': '2026-01-08', 'coverage': COVERAGE}

        def changes(self, after_seq):
            items = []
            for day in ('2026-01-06', '2026-01-08'):
                item = {'date': day, 'policy_id': 'new-currency-policy', 'policy_hash': 'b' * 64,
                        'values': {'CAD': '1.400000000000000000', 'USD': '1'}, 'observation_ids': [],
                        'coverage': ['CAD', 'USD'], 'observation_dates': {'CAD': day},
                        'statuses': {'CAD': 'completed', 'USD': 'completed'}, 'hash_version': 2}
                items.append({**item, 'snapshot_id': day, 'sources': {'CAD': ['ecb']},
                              'content_hash': resolver.snapshot_hash(item)})
            yield {'release_id': 'cad-release', 'after_seq': after_seq, 'items': items, 'next_cursor': None}
    return Client()


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
def test_new_currency_feed_resolves_without_consumer_tree_change():
    from rentals.services.fx_mirror import sync, get_rate, capture
    state = sync(client())
    assert state.coverage == COVERAGE
    assert state.max_fiat_age_days == 14
    assert capture().state['coverage'] == COVERAGE
    assert get_rate('CAD', 'CAD', date(2026, 1, 8))['FX'] == Decimal('1')
    assert get_rate('USD', 'CAD', date(2026, 1, 8))['FX'] == Decimal('1.4')
    assert get_rate('CAD', 'USD', date(2026, 1, 8))['FX'] == Decimal('0.714285714285714286')


@pytest.mark.django_db
@override_settings(FX_BACKEND='mirror')
@pytest.mark.parametrize('currency,day,code', [('CAD', '2026-01-05', 'before_coverage'),
                                             ('CAD', '2026-01-07', 'outside_applicability'),
                                             ('XYZ', '2026-01-08', 'unsupported_currency')])
def test_release_coverage_errors_remain_distinct(currency, day, code):
    from rentals.services.fx_mirror import sync, get_rate
    from rentals.services.fx import MissingFXRate
    sync(client())
    with pytest.raises(MissingFXRate) as error:
        get_rate(currency, currency, date.fromisoformat(day))
    assert error.value.code == code


@pytest.mark.django_db
def test_same_release_sync_populates_metadata_after_schema_upgrade():
    from rentals.models import FXSyncState
    from rentals.services.fx_mirror import sync
    sync(client())
    FXSyncState.objects.filter(pk=1).update(coverage={})
    refreshed = sync(client())
    assert refreshed.coverage == COVERAGE
    assert FXSyncState.objects.get(pk=1).coverage == COVERAGE
