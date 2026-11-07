import hashlib
import json
from datetime import datetime
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
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


BEHAVIORAL_DIFFERENCES = [
    {'cause': 'rent_total_face_value', 'locations': ['rentals/models.py::Tenant.rent_total'], 'why': 'Mirror converts each payment to the property/target currency; legacy sums mixed currencies at face value when the target is native or omitted.'},
    {'cause': 'scheduler_rent_denomination', 'locations': ['rentals/services/scheduler.py::debt'], 'why': 'Mirror converts each contractual rent to property currency on its due date; legacy treats the lease amount as property currency. Grace windows and due dates are unchanged.'},
    {'cause': 'scheduler_rent_selection', 'locations': ['rentals/services/scheduler.py::debt', 'rentals/models.py::Tenant.lease_rent'], 'why': 'For tied effective dates, the mirror scheduler selects descending primary key to make the latest recorded rent deterministic; legacy orders by date alone, so its selected amount is database-dependent. This can affect same-currency rent without any FX change.'},
    {'cause': 'native_stats_and_pnl', 'locations': ['rentals/api/views.py::PropertyViewSet.with_stats', 'rentals/services/financials.py::pnl_calc'], 'why': 'Mirror converts foreign transactions even in native-property presentation; legacy sums their face values. Business transaction amounts and currencies are unchanged.'},
    {'cause': 'identity_requires_coverage', 'locations': ['rentals/services/fx.py::convert', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'Mirror requires supported dated coverage even for identity conversion; legacy returns one without reference data.'},
    {'cause': 'typed_missing_tenant_fx', 'locations': ['rentals/analytics/tenant.py::_converted'], 'why': 'Missing conversion is a typed row issue with null affected values/opening/cumulative totals; it cannot produce an apparently complete total. Other aggregate reports fail explicitly with missing_fx.'},
    {'cause': 'provisional_completed_day', 'locations': ['rentals/services/fx_mirror.py::get_rate', 'rentals/api/views.py::_consistent_fx_report', 'rentals/api/analytics_views.py::_PortfolioAnalyticsView'], 'why': 'Through business today, a fresh latest completed snapshot may value provisionally; affected responses are labeled and not cacheable. Future/stale dates fail.'},
    {'cause': 'canonical_reference_policy', 'locations': ['rentals/services/fx.py::get_rate', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'One dated anchor ratio replaces legacy shortest paths and independently dated edges, unbounded historical carry and local/manual rows. Fixed pegs and currency applicability follow initial-v1.'},
    {'cause': 'decimal_precision', 'locations': ['rentals/services/fx.py::convert', 'rentals/services/fx.py::PreloadedConverter', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'Mirror uses isolated precision 38 / ROUND_HALF_UP and 18-place multipliers rather than legacy ambient-context arithmetic and stored-rate precision. Native monetary rounding remains unchanged.'},
]


def behavioral_causes(kind, obj, currency, target):
    causes = ['canonical_reference_policy', 'decimal_precision', 'provisional_completed_day']
    if currency == target:
        causes.append('identity_requires_coverage')
    if kind in {'lease_rent', 'lease_due'}:
        if currency != obj.tenant.property.currency:
            causes.append('scheduler_rent_denomination')
        if obj.tenant.rent_history.filter(date_rent_set=obj.date_rent_set).exclude(pk=obj.pk).exists():
            causes.append('scheduler_rent_selection')
        causes.append('typed_missing_tenant_fx')
    if kind == 'transaction':
        if currency != obj.property.currency and target == obj.property.currency:
            causes.append('native_stats_and_pnl')
            if obj.category == 'rent':
                causes.append('rent_total_face_value')
        if obj.category == 'rent':
            causes.append('typed_missing_tenant_fx')
    return causes


def business_hash(obj):
    values = {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}
    return hashlib.sha256(json.dumps(values, default=str, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def multiplier_difference_cause(legacy, mirror):
    if (legacy is None) != (mirror is None):
        return 'reference_coverage'
    if legacy is None or Decimal(legacy) == Decimal(mirror):
        return None
    with localcontext(Context(prec=38, rounding=ROUND_HALF_UP)):
        if Decimal(legacy).quantize(Decimal('0.000000000000000001')) == Decimal(mirror):
            return 'decimal_precision'
    return 'canonical_reference_policy'


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
                        legacy, mirror = result['legacy_multiplier'], result['mirror_multiplier']
                        result['multiplier_difference_cause'] = multiplier_difference_cause(legacy, mirror)
                        result['applicable_behavioral_causes'] = behavioral_causes(kind, obj, currency, target)
                        records.append(result)
                    obj.refresh_from_db()
                    if business_hash(obj) != before:
                        raise CommandError('Business data changed during comparison')
                after_state = FXSyncState.objects.filter(pk=1).values('release_id', 'seq', 'history_epoch').first()
                if before_state == after_state:
                    output = {'release': before_state, 'behavioral_differences': BEHAVIORAL_DIFFERENCES, 'records': records}
                    break
        else:
            raise CommandError('FX release changed during comparison')
        Path(options['output']).write_text(json.dumps(output, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
        self.stdout.write('FX comparison exported')
