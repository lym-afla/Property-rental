"""Bounded local browsing; provenance reads alone use the shared service."""

from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.core import signing
from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from rentals.api.serializers import FXBrowseSerializer
from rentals.models import FXAnchor, FXSyncState
from rentals.services.fx import MissingFXRate
from rentals.services.fx_client import FXClient
from rentals.services.fx_mirror import get_rate

_SALT = 'rent.fx.browse.v1'
_MAX_TOKEN = 6000
_MAX_AGE = 86400
_PARENTS = {'EUR': 'USD', 'RUB': 'USD', 'GBP': 'EUR', 'CHF': 'EUR', 'PLN': 'EUR', 'CNY': 'EUR', 'USDT': 'USD', 'USDC': 'USD'}


def _token(value, purpose):
    encoded = signing.dumps(value, salt=_SALT + purpose, compress=True)
    if len(encoded) > _MAX_TOKEN:
        raise ValidationError('Selected FX range is too large. Choose fewer dates.')
    return encoded


def _decode(value, purpose):
    if not value or len(value) > _MAX_TOKEN:
        raise ValidationError('Invalid FX cursor. Refresh the range.')
    try:
        return signing.loads(value, salt=_SALT + purpose, max_age=_MAX_AGE)
    except signing.BadSignature:
        raise ValidationError('Expired or invalid FX cursor. Refresh the range.')


def _path(base, quote):
    def ancestors(currency):
        result = [currency]
        while currency in _PARENTS:
            currency = _PARENTS[currency]
            result.append(currency)
        return result
    left, right = ancestors(base), ancestors(quote)
    common = next(currency for currency in left if currency in right)
    return left[:left.index(common)] + list(reversed(right[:right.index(common) + 1]))


def _row(base, quote, day, release_id):
    path = _path(base, quote)
    sources = sorted({
        'CBR' if 'RUB' in (a, b) else 'Fixed peg policy' if {'USDT', 'USDC'} & {a, b} else 'ECB'
        for a, b in zip(path, path[1:])
    })
    row = {'date': day.isoformat(), 'from_currency': base, 'to_currency': quote,
           'direction': f'{quote} per {base}', 'release_id': release_id,
           'kind': 'identity' if base == quote else 'direct' if len(path) == 2 else 'derived',
           'path': path, 'sources': sources, 'rate': None, 'error': None,
           'snapshot_id': None, 'observation_date': None, 'carried_forward': False,
           'provisional': False, 'effective_date': None}
    try:
        result = get_rate(base, quote, day)
        anchors = list(FXAnchor.objects.filter(date=result['effective_date'], currency__in=[base, quote]))
        snapshots = {anchor.snapshot_id for anchor in anchors}
        if len(snapshots) != 1:
            raise MissingFXRate('Inconsistent FX snapshot')
        observed = [anchor.observation_date for anchor in anchors if anchor.observation_date]
        row.update(rate=str(result['FX']), snapshot_id=snapshots.pop(),
                   effective_date=result['effective_date'].isoformat(),
                   observation_date=min(observed).isoformat() if observed else None,
                   carried_forward=any(observation < day for observation in observed),
                   provisional=result['provisional'])
    except MissingFXRate as exc:
        row['error'] = 'missing_fx' if exc.code == 'missing_rate' else exc.code
    return row


def browse(request):
    if 'cursor' in request.query_params:
        if set(request.query_params) != {'cursor'}:
            raise ValidationError('A cursor cannot be combined with new filters. Refresh the range.')
        snapshot = _decode(request.query_params['cursor'], 'page')
    else:
        params = FXBrowseSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        values = params.validated_data
        with transaction.atomic():
            # Sync locks this same row before replacing anchors, preventing a
            # promotion between the release read and snapshot materialization.
            state = FXSyncState.objects.select_for_update().filter(pk=1).first()
            latest = FXAnchor.objects.aggregate(latest=Max('date'))['latest']
            rows = []
            if state and latest:
                end = values.get('end', latest)
                start = values.get('start', end - timedelta(days=30))
                if not 0 <= (end - start).days <= 30:
                    raise ValidationError('Choose a date range of 1 to 31 days.')
                rows = [_row(values['base'], values['quote'], end - timedelta(days=offset), state.release_id)
                        for offset in range((end - start).days + 1)]
            snapshot = {'backend': 'mirror', 'release_id': state.release_id if state else None,
                        'status': 'ok' if rows else 'empty' if state else 'unsynced',
                        'rows': rows, 'offset': 0, 'page_size': values['page_size']}
    offset, size = snapshot['offset'], snapshot['page_size']
    rows = snapshot['rows'][offset:offset + size]
    results = [dict(row, details_token=_token(row, 'details') if row['rate'] is not None else None) for row in rows]
    next_url = None
    if offset + size < len(snapshot['rows']):
        continuation = dict(snapshot, offset=offset + size)
        next_url = request.path + '?' + urlencode({'cursor': _token(continuation, 'page')})
    response = Response({key: snapshot[key] for key in ('backend', 'release_id', 'status')} | {
        'count': len(snapshot['rows']),
        'first': request.path + '?' + urlencode({'cursor': _token(dict(snapshot, offset=0), 'page')}),
        'next': next_url, 'results': results,
    })
    response['Cache-Control'] = 'no-store'
    return response


def details(request):
    pinned = _decode(request.query_params.get('token'), 'details')
    query = {'base': pinned['from_currency'], 'quote': pinned['to_currency'], 'date': pinned['date']}
    try:
        batch = FXClient().rates(pinned['release_id'], [query])
        result, = batch['results']
        if (result['release_id'] != pinned['release_id']
                or result['snapshot_id'] != pinned['snapshot_id']
                or result.get('error') or result['multiplier'] != pinned['rate']):
            raise ValueError('Provenance does not match the browsed snapshot')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return Response({'code': 'fx_details_unavailable', 'detail': 'Provenance is temporarily unavailable. The table retains its synced rates.'}, status=503)
    response = Response({'status': 'ok', 'result': result})
    response['Cache-Control'] = 'no-store'
    return response
