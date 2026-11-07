import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
import networkx as nx

from rentals.analytics.tenant import _due_dates, _effective_rate
from rentals.constants import CURRENCY_CHOICES
from rentals.models import DepositMovement, FXSyncState, Lease_rent, Property_capital_structure, Tenant, Transaction
from rentals.services.fx import get_rate


def business_hash(obj):
    values = {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}
    return hashlib.sha256(json.dumps(values, default=str, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def comparison_rows():
    for model, kind, date_field, currency_field in (
        (Transaction, 'transaction', 'date', 'currency'),
        (DepositMovement, 'deposit', 'date', 'currency'),
        (Property_capital_structure, 'capital', 'capital_structure_date', 'property.currency'),
        (Lease_rent, 'lease_rent', 'date_rent_set', 'currency'),
    ):
        for obj in model.objects.order_by('pk').iterator():
            currency = obj.property.currency if currency_field == 'property.currency' else getattr(obj, currency_field)
            yield kind, obj, getattr(obj, date_field), currency
    today = datetime.now(ZoneInfo(settings.BUSINESS_TIME_ZONE)).date()
    for tenant in Tenant.objects.order_by('pk').iterator():
        rates = tuple(tenant.rent_history.order_by('date_rent_set', 'pk'))
        for due in _due_dates(tenant, tenant.lease_start, today):
            rate = _effective_rate(rates, due)
            if rate:
                yield 'lease_due', rate, due, rate.currency


class Command(BaseCommand):
    help = 'Export hashed business facts and both FX multipliers.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        for attempt in range(2):
            with transaction.atomic():
                before_state = FXSyncState.objects.filter(pk=1).values('release_id', 'seq', 'history_epoch').first()
                records = []
                for kind, obj, as_of, currency in comparison_rows():
                    before = business_hash(obj)
                    for target, _ in CURRENCY_CHOICES:
                        result = {'kind': kind, 'business_hash': before, 'date': as_of.isoformat(), 'currency': currency, 'target_currency': target}
                        for backend in ('legacy', 'mirror'):
                            try:
                                with override_settings(FX_BACKEND=backend):
                                    multiplier = get_rate(currency, target, as_of)['FX']
                                result[f'{backend}_multiplier'] = str(multiplier)
                            except (ValueError, LookupError, nx.NetworkXException):
                                result[f'{backend}_multiplier'] = None
                        records.append(result)
                    obj.refresh_from_db()
                    if business_hash(obj) != before:
                        raise CommandError('Business data changed during comparison')
                after_state = FXSyncState.objects.filter(pk=1).values('release_id', 'seq', 'history_epoch').first()
                if before_state == after_state:
                    output = {'release': before_state, 'records': records}
                    break
        else:
            raise CommandError('FX release changed during comparison')
        Path(options['output']).write_text(json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
        self.stdout.write('FX comparison exported')
