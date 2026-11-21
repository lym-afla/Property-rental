from datetime import date
from decimal import Decimal
import json

from django.core.management import call_command
import pytest

from rentals.models import FX, FXAnchor, FXSyncState
from rentals.tests.factories import TransactionFactory


@pytest.mark.django_db(transaction=True)
def test_comparison_exports_actual_fix_time_inputs_and_explicit_missing_evidence(tmp_path):
    day = date(2026, 1, 6)
    row = TransactionFactory(currency='EUR', amount=Decimal('10'), date=day)
    FXSyncState.objects.create(pk=1, release_id='release', seq=1, history_epoch=1)
    for currency, value, observed, status in [
        ('USD', '1', None, 'completed'),
        ('EUR', '0.9', date(2026, 1, 5), 'carried'),
        ('RUB', '95', day, 'completed'),
    ]:
        FXAnchor.objects.create(date=day, currency=currency, value=value, observation_date=observed,
                                snapshot_id='snapshot', status=status)
    FX.objects.create(date=day, from_currency='EUR', to_currency='USD', rate=Decimal('1'))
    FX.objects.create(date=day, from_currency='USD', to_currency='RUB', rate=Decimal('90'))
    output = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(output), as_of=day)
    exported = json.loads(output.read_text())
    record = next(r for r in exported['records'] if r['kind'] == 'transaction' and r['record_id'] == str(row.pk) and r['target_currency'] == 'RUB')
    assert record['multiplier_difference_cause'] == 'unseparated_reference_policy_and_fix_time'
    assert record['fix_time_inputs'] == {
        'status': 'unavailable', 'reason': 'fixing_time_aligned_reference_unavailable',
        'release_id': 'release', 'effective_date': '2026-01-06',
        'anchors': {
            'EUR': {'value': '0.9', 'observation_date': '2026-01-05', 'snapshot_id': 'snapshot', 'status': 'carried'},
            'RUB': {'value': '95', 'observation_date': '2026-01-06', 'snapshot_id': 'snapshot', 'status': 'completed'},
        },
        'missing': ['cbr_fixing_timestamp', 'non_usd_usd_quote_at_cbr_fixing_time'],
    }
    usd = next(r for r in exported['records'] if r['kind'] == 'transaction' and r['record_id'] == str(row.pk) and r['target_currency'] == 'USD')
    assert 'fix_time_inputs' not in usd
    assert usd['multiplier_difference_cause'] == 'canonical_reference_policy'
    assert 'fix_time_mismatch' in {entry['cause'] for entry in exported['behavioral_differences']}
    assert 'fix_time_mismatch' in record['applicable_behavioral_causes']
    assert 'fix_time_mismatch' not in usd['applicable_behavioral_causes']
