from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, DecimalException
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import connection, transaction
from django.utils.dateparse import parse_datetime

from rentals.models import FXAnchor
from rentals.services.fx import MissingFXRate
from rentals.services import shared_fx_resolver as resolver

report_provisional = ContextVar("fx_report_provisional", default=None)

_snapshot_context = ContextVar('fx_snapshot_context', default=None)


@dataclass(frozen=True)
class MirrorAnchor:
    value: str
    observation_date: date | None
    snapshot_id: str
    status: str


@dataclass(frozen=True)
class MirrorSnapshot:
    state: dict | None
    anchors: dict
    latest: date | None


def capture(requested=None, currencies=None):
    condition, params = 'TRUE', []
    if requested is not None:
        condition += ' AND a.date IN (%s,m.latest_date)'
        params.append(requested)
    if currencies is not None:
        condition += ' AND a.currency IN (' + ','.join(['%s'] * len(currencies)) + ')'
        params.extend(currencies)
    with transaction.atomic(savepoint=False), connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT s.release_id,s.seq,s.history_epoch,s.synced_at,
                   a.date,a.currency,a.value,a.observation_date,a.snapshot_id,a.status,m.latest_date
            FROM (SELECT max(date) AS latest_date FROM rentals_fxanchor) m
            LEFT JOIN rentals_fxsyncstate s ON s.id=1
            LEFT JOIN rentals_fxanchor a ON {condition}
            ORDER BY a.date,a.currency
        """, params)
        rows = cursor.fetchall()
    state = None
    anchors = {}
    for release_id, seq, epoch, synced_at, day, currency, value, observed, snapshot, status, latest in rows:
        if release_id is not None and state is None:
            state = {'release_id': release_id, 'seq': seq, 'history_epoch': epoch,
                     'synced_at': parse_datetime(synced_at) if isinstance(synced_at, str) else synced_at}
        if day is not None:
            day = date.fromisoformat(day) if isinstance(day, str) else day
            observed = date.fromisoformat(observed) if isinstance(observed, str) else observed
            anchors.setdefault(day, {})[currency] = MirrorAnchor(value, observed, snapshot, status)
    latest = date.fromisoformat(latest) if isinstance(latest, str) else latest
    return MirrorSnapshot(state, anchors, latest)


@contextmanager
def pinned(snapshot=None):
    selected = snapshot or _snapshot_context.get() or capture()
    token = _snapshot_context.set(selected)
    try:
        yield selected
    finally:
        _snapshot_context.reset(token)


def get_rate(base, quote, requested):
    today = datetime.now(ZoneInfo(getattr(settings, 'BUSINESS_TIME_ZONE', 'Europe/Moscow'))).date()
    try:
        resolver.select_date(requested, None)
        snapshot = _snapshot_context.get() or capture(requested, (base, quote))
        selection = resolver.select_date(requested, snapshot.latest)
        anchors = {currency: anchor for currency, anchor in snapshot.anchors.get(selection.effective_date, {}).items()
                   if currency in {base, quote}}
        resolved = resolver.resolve(
            {currency: Decimal(anchor.value) for currency, anchor in anchors.items()},
            base, quote, requested, latest_completed_date=snapshot.latest, business_today=today,
            observation_dates={currency: anchor.observation_date for currency, anchor in anchors.items()
                               if anchor.observation_date is not None},
            statuses={currency: anchor.status for currency, anchor in anchors.items()},
        )
    except resolver.ContractError as error:
        raise MissingFXRate(str(error), error.code) from error
    except DecimalException as error:
        raise MissingFXRate('Invalid FX anchor', 'invalid_rate') from error
    if resolved.provisional and report_provisional.get() is not None:
        report_provisional.get().add(resolved.effective_date.isoformat())
    return {'FX': resolved.multiplier, 'conversions': int(base != quote), 'dates_async': False,
            'dates': [resolved.effective_date], 'FX dates used': [resolved.effective_date],
            'effective_date': resolved.effective_date, 'source_date': resolved.source_date,
            'statuses': {currency: anchor.status for currency, anchor in anchors.items()},
            'provisional': resolved.provisional, 'cacheable': resolved.cacheable}


_POLICY_ID = 'initial-v1'
_POLICY_HASH = 'dcec25ddeff179e638416303494a030795f7d99883a646634894d1867c2e3aae'


def _feed(client, release_id, after_seq):
    previous_date = None
    ended = False
    for page in client.changes(after_seq):
        if ended or page['release_id'] != release_id or page['after_seq'] != after_seq:
            raise ValueError('Invalid FX changes page')
        for item in page['items']:
            item = resolver.check_snapshot(item)
            if item['policy_id'] != _POLICY_ID or item['policy_hash'] != _POLICY_HASH:
                raise ValueError('Unsupported FX snapshot policy')
            if previous_date is not None and item['date'] <= previous_date:
                raise ValueError('Invalid FX snapshot')
            date.fromisoformat(item['date'])
            previous_date = item['date']
            if not item['snapshot_id'] or not isinstance(item['sources'], dict):
                raise ValueError('Invalid FX snapshot')
            yield item
        ended = page['next_cursor'] is None
    if not ended:
        raise ValueError('Incomplete FX changes')


def _coverage(assignments):
    result = {}
    latest = None
    for day, currency, value, observed, snapshot, status in sorted(assignments, key=lambda row: (row[1], row[0])):
        day = date.fromisoformat(day)
        latest = max(latest, day) if latest else day
        intervals = result.setdefault(currency, [])
        if intervals and day == intervals[-1][1] + timedelta(days=1):
            intervals[-1][1] = day
        else:
            intervals.append([day, day])
    return ({currency: [{'start': start.isoformat(), 'end': end.isoformat()} for start, end in intervals] for currency, intervals in result.items()}, latest.isoformat() if latest else None)


def _assignments(item):
    return {(item['date'], currency, value, item['observation_dates'].get(currency), item['snapshot_id'], item['statuses'][currency]) for currency, value in item['values'].items()}


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
                         observation_date=item['observation_dates'].get(currency), snapshot_id=item['snapshot_id'], status=item['statuses'][currency])
                for currency, value in item['values'].items()
            ])
        staged = {(day.isoformat(), currency, value, observed.isoformat() if observed else None, snapshot, status)
                  for day, currency, value, observed, snapshot, status in FXAnchor.objects.values_list('date', 'currency', 'value', 'observation_date', 'snapshot_id', 'status')}
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
