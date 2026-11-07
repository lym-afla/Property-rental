from contextvars import ContextVar
from datetime import date, datetime, timedelta
from decimal import Context, Decimal, DecimalException, ROUND_HALF_UP, localcontext
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Max

from rentals.models import FXAnchor
from rentals.services.fx import MissingFXRate

report_provisional = ContextVar("fx_report_provisional", default=None)

# Initial contract applicability. The feed does not carry policy applicability;
# changing these dates requires coordinating the service contract and consumer.
_COVERAGE_START = {
    'USD': date(1998, 1, 1), 'RUB': date(1998, 1, 1),
    'USDT': date(1998, 1, 1), 'USDC': date(1998, 1, 1),
    'EUR': date(1999, 1, 4), 'GBP': date(1999, 1, 4),
    'CHF': date(1999, 1, 4), 'PLN': date(1999, 1, 4),
    'CNY': date(2000, 1, 13),
}


def get_rate(base, quote, requested):
    if any(currency not in _COVERAGE_START for currency in (base, quote)):
        raise MissingFXRate('Unsupported FX currency', 'unsupported_currency')
    if any(requested < _COVERAGE_START[currency] for currency in (base, quote)):
        raise MissingFXRate('FX date is before currency coverage', 'before_coverage')
    latest = FXAnchor.objects.aggregate(latest=Max('date'))['latest']
    if latest is None:
        raise MissingFXRate('FX mirror has no release')
    effective = requested
    if requested > latest:
        today = datetime.now(ZoneInfo(getattr(settings, 'BUSINESS_TIME_ZONE', 'Europe/Moscow'))).date()
        if requested > today:
            raise MissingFXRate('FX date is in the future', 'future_date')
        effective = latest
    anchors = {row.currency: row for row in FXAnchor.objects.filter(date=effective, currency__in=[base, quote])}
    if base not in anchors or quote not in anchors:
        raise MissingFXRate(f'FX rate for {base} to {quote} not found.')
    if requested > latest and base != quote:
        for currency, anchor in anchors.items():
            if currency not in {'USD', 'USDT', 'USDC'}:
                if anchor.observation_date is None:
                    raise MissingFXRate('FX observation is unavailable')
                if anchor.observation_date > effective:
                    raise MissingFXRate('FX observation is newer than its snapshot', 'future_observation')
                if (requested - anchor.observation_date).days > 14:
                    raise MissingFXRate('FX observation is stale', 'stale')
    try:
        with localcontext(Context(prec=38, rounding=ROUND_HALF_UP)):
            values = [Decimal(anchors[currency].value) for currency in (base, quote)]
            if any(not value.is_finite() or value <= 0 for value in values):
                raise MissingFXRate('Invalid FX anchor', 'invalid_rate')
            multiplier = (values[1] / values[0]).quantize(Decimal('0.000000000000000001'))
            if multiplier <= 0:
                raise MissingFXRate('Invalid FX rate', 'invalid_rate')
    except DecimalException as exc:
        raise MissingFXRate('Invalid FX rate', 'invalid_rate') from exc
    if requested > latest and report_provisional.get() is not None:
        report_provisional.get().add(effective.isoformat())
    return {'FX': multiplier, 'conversions': int(base != quote), 'dates_async': False, 'dates': [effective], 'FX dates used': [effective], 'effective_date': effective, 'provisional': requested > latest, 'cacheable': requested <= latest}



_POLICY_ID = 'initial-v1'
_POLICY_HASH = 'dc402fff8264f862325f6ad33bf34ff2a8d3d02ef82f5f66ec1ee6351a2eefd5'


def _feed(client, release_id, after_seq):
    import hashlib
    import json

    previous_date = None
    ended = False
    for page in client.changes(after_seq):
        if ended or page['release_id'] != release_id or page['after_seq'] != after_seq:
            raise ValueError('Invalid FX changes page')
        for item in page['items']:
            keys = ('date', 'policy_id', 'policy_hash', 'values', 'observation_ids', 'coverage', 'observation_dates')
            canonical = {key: item[key] for key in keys}
            digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
            if item['policy_id'] != _POLICY_ID or item['policy_hash'] != _POLICY_HASH:
                raise ValueError('Unsupported FX snapshot policy')
            if digest != item['content_hash'] or (previous_date is not None and item['date'] <= previous_date):
                raise ValueError('Invalid FX snapshot')
            date.fromisoformat(item['date'])
            previous_date = item['date']
            if sorted(item['coverage']) != sorted(item['values']) or item['coverage'] != sorted(set(item['coverage'])) or item['observation_ids'] != sorted(set(item['observation_ids'])):
                raise ValueError('Invalid FX coverage')
            if not item['snapshot_id'] or not isinstance(item['sources'], dict):
                raise ValueError('Invalid FX snapshot')
            for currency, value in item['values'].items():
                number = Decimal(value)
                if not number.is_finite() or number <= 0:
                    raise ValueError('Invalid FX anchor')
            yield item
        ended = page['next_cursor'] is None
    if not ended:
        raise ValueError('Incomplete FX changes')


def _coverage(assignments):
    result = {}
    latest = None
    for day, currency, value, observed, snapshot in sorted(assignments, key=lambda row: (row[1], row[0])):
        day = date.fromisoformat(day)
        latest = max(latest, day) if latest else day
        intervals = result.setdefault(currency, [])
        if intervals and day == intervals[-1][1] + timedelta(days=1):
            intervals[-1][1] = day
        else:
            intervals.append([day, day])
    return ({currency: [{'start': start.isoformat(), 'end': end.isoformat()} for start, end in intervals] for currency, intervals in result.items()}, latest.isoformat() if latest else None)


def _assignments(item):
    return {(item['date'], currency, value, item['observation_dates'].get(currency), item['snapshot_id']) for currency, value in item['values'].items()}


def sync(client):
    from django.db import transaction
    from rentals.models import FXSyncState

    release = client.current_release()
    required = {'id', 'seq', 'predecessor_id', 'chain_hash', 'history_epoch', 'policy_id', 'max_fiat_age_days', 'coverage', 'latest_completed_date'}
    if not isinstance(release, dict) or not required.issubset(release):
        raise ValueError('Missing FX release metadata')
    if not isinstance(release['chain_hash'], str) or not release['chain_hash']:
        raise ValueError('Missing FX release chain hash')
    if release['policy_id'] != _POLICY_ID or release['max_fiat_age_days'] != 14:
        raise ValueError('Unsupported FX release policy')
    expected = release['coverage']
    latest = release['latest_completed_date']
    if not isinstance(expected, dict) or not expected or not isinstance(latest, str):
        raise ValueError('Missing FX release coverage')
    date.fromisoformat(latest)
    with transaction.atomic():
        state = FXSyncState.objects.select_for_update().filter(pk=1).first()
        after_seq = state.seq if state else 0
        if release['seq'] < after_seq or (state and release['history_epoch'] < state.history_epoch):
            raise ValueError('FX release sequence or epoch moved backwards')
        if release['seq'] == after_seq:
            if not state or state.release_id != release['id'] or state.history_epoch != release['history_epoch']:
                raise ValueError('FX release sequence conflicts')
            return state
        for item in _feed(client, release['id'], after_seq):
            FXAnchor.objects.filter(date=item['date']).delete()
            FXAnchor.objects.bulk_create([
                FXAnchor(date=item['date'], currency=currency, value=value,
                         observation_date=item['observation_dates'].get(currency), snapshot_id=item['snapshot_id'])
                for currency, value in item['values'].items()
            ])
        staged = {(day.isoformat(), currency, value, observed.isoformat() if observed else None, snapshot)
                  for day, currency, value, observed, snapshot in FXAnchor.objects.values_list('date', 'currency', 'value', 'observation_date', 'snapshot_id')}
        if _coverage(staged) != (expected, latest):
            raise ValueError('Incomplete FX coverage')
        if state and release['history_epoch'] != state.history_epoch:
            audited = set()
            for item in _feed(client, release['id'], 0):
                audited.update(_assignments(item))
            if _coverage(audited) != (expected, latest) or audited != staged:
                raise ValueError('Incomplete FX correction')
        state, _ = FXSyncState.objects.update_or_create(pk=1, defaults={'release_id': release['id'], 'seq': release['seq'], 'history_epoch': release['history_epoch']})
        return state
