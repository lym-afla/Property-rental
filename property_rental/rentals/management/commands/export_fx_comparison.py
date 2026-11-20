import hashlib
import json
import os
from datetime import date, datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
import networkx as nx

from rentals.analytics.tenant import _due_dates, _effective_rate
from rentals.constants import CURRENCY_CHOICES
from rentals.models import DepositMovement, FXAnchor, FXSyncState, Lease_rent, Property, Property_capital_structure, Tenant, Transaction
from rentals.services.fx import get_rate
from rentals.services.fx_mirror import pinned
from rentals.services.fx_context import calculation_context, backend
from rentals.services.fx_comparison import build_reports, report_scope, FAMILIES


BEHAVIORAL_DIFFERENCES = [
    {'cause': 'rent_total_face_value', 'locations': ['rentals/models.py::Tenant.rent_total'], 'why': 'Mirror converts each payment to the property/target currency; legacy sums mixed currencies at face value when the target is native or omitted.'},
    {'cause': 'scheduler_rent_denomination', 'locations': ['rentals/services/scheduler.py::debt'], 'why': 'Mirror converts each contractual rent to property currency on its due date; legacy treats the lease amount as property currency. Grace windows and due dates are unchanged.'},
    {'cause': 'scheduler_rent_selection', 'locations': ['rentals/services/scheduler.py::debt', 'rentals/models.py::Tenant.lease_rent'], 'why': 'For tied effective dates, the mirror scheduler selects descending primary key to make the latest recorded rent deterministic; legacy orders by date alone, so its selected amount is database-dependent. This can affect same-currency rent without any FX change.'},
    {'cause': 'native_stats_and_pnl', 'locations': ['rentals/api/views.py::PropertyViewSet.with_stats', 'rentals/services/financials.py::pnl_calc'], 'why': 'Mirror converts foreign transactions even in native-property presentation; legacy sums their face values. Business transaction amounts and currencies are unchanged.'},
    {'cause': 'identity_requires_coverage', 'locations': ['rentals/services/fx.py::convert', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'Mirror requires supported dated coverage even for identity conversion; legacy returns one without reference data.'},
    {'cause': 'typed_missing_tenant_fx', 'locations': ['rentals/analytics/tenant.py::_converted'], 'why': 'Missing conversion is a typed row issue with null affected values/opening/cumulative totals; it cannot produce an apparently complete total. Other aggregate reports fail explicitly with missing_fx.'},
    {'cause': 'provisional_completed_day', 'locations': ['rentals/services/fx_mirror.py::get_rate', 'rentals/api/views.py::_consistent_fx_report', 'rentals/api/analytics_views.py::_PortfolioAnalyticsView'], 'why': 'Through business today, a fresh latest completed snapshot may value provisionally; affected responses are labeled and not cacheable. Future/stale dates fail.'},
    {'cause': 'canonical_reference_policy', 'locations': ['rentals/services/fx.py::get_rate', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'One dated anchor ratio replaces legacy shortest paths and independently dated edges, unbounded historical carry and local/manual rows. Fixed pegs and currency applicability follow initial-v1.'},
    {'cause': 'fix_time_mismatch', 'locations': ['rentals/management/commands/export_fx_comparison.py::fix_time_inputs'], 'why': 'RUB crosses combine the CBR effective-date rate with later ECB fixes. Calendar-date anchors cannot isolate timing from reference-policy movement; aligned quotes and their fixing timestamps are required.'},
    {'cause': 'decimal_precision', 'locations': ['rentals/services/fx.py::convert', 'rentals/services/fx.py::PreloadedConverter', 'rentals/services/fx_mirror.py::get_rate'], 'why': 'Mirror uses isolated precision 38 / ROUND_HALF_UP and 18-place multipliers rather than legacy ambient-context arithmetic and stored-rate precision. Native monetary rounding remains unchanged.'},
]


def is_rub_fiat_cross(base, quote):
    return (base == 'RUB' and quote in {'EUR', 'GBP', 'CHF', 'PLN', 'CNY'}) or (quote == 'RUB' and base in {'EUR', 'GBP', 'CHF', 'PLN', 'CNY'})


def fix_time_inputs(base, quote, effective_date):
    anchors = {}
    if effective_date is not None:
        anchors = {anchor.currency: {'value': anchor.value,
                    'observation_date': anchor.observation_date.isoformat() if anchor.observation_date else None,
                    'snapshot_id': anchor.snapshot_id, 'status': anchor.status}
                   for anchor in FXAnchor.objects.filter(date=effective_date, currency__in=[base, quote])}
    return {'status': 'unavailable', 'reason': 'fixing_time_aligned_reference_unavailable',
            'release_id': getattr(FXSyncState.objects.filter(pk=1).first(), 'release_id', None),
            'effective_date': effective_date.isoformat() if effective_date else None, 'anchors': anchors,
            'missing': ['cbr_fixing_timestamp', 'non_usd_usd_quote_at_cbr_fixing_time']}


def behavioral_causes(kind, obj, currency, target):
    causes = ['canonical_reference_policy', 'decimal_precision', 'provisional_completed_day']
    if is_rub_fiat_cross(currency, target):
        causes.append('fix_time_mismatch')
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


def comparison_rows(as_of):
    for model, kind, date_field, currency_field in (
        (Transaction, 'transaction', 'date', 'currency'),
        (DepositMovement, 'deposit', 'date', 'currency'),
        (Property_capital_structure, 'capital', 'capital_structure_date', 'property.currency'),
        (Lease_rent, 'lease_rent', 'date_rent_set', 'currency'),
    ):
        for obj in model.objects.order_by('pk').iterator():
            currency = obj.property.currency if currency_field == 'property.currency' else getattr(obj, currency_field)
            yield kind, obj, getattr(obj, date_field), currency
    today = as_of
    for tenant in Tenant.objects.order_by('pk').iterator():
        rates = tuple(tenant.rent_history.order_by('date_rent_set', 'pk'))
        for due in _due_dates(tenant, tenant.lease_start, today):
            rate = _effective_rate(rates, due)
            if rate:
                yield 'lease_due', rate, due, rate.currency


def read_only(execute, sql, params, many, context):
    if sql.strip().upper() == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY':
        return execute(sql, params, many, context)
    if sql.lstrip().split(None, 1)[0].upper() not in {'SELECT', 'BEGIN', 'SAVEPOINT', 'RELEASE', 'ROLLBACK'}:
        raise CommandError('comparison_write_forbidden')
    return execute(sql, params, many, context)


class Command(BaseCommand):
    help = 'Export private business evidence and measured live report counterfactuals.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)
        parser.add_argument('--source-commit', default=os.environ.get('FX_EXPORT_SOURCE_COMMIT'))
        parser.add_argument('--image-digest', default=os.environ.get('FX_EXPORT_IMAGE_DIGEST'))
        parser.add_argument('--as-of', type=date.fromisoformat)
        parser.add_argument('--report-start', type=date.fromisoformat)
        parser.add_argument('--report-currency', choices=[c for c, _ in CURRENCY_CHOICES], default='USD')

    def handle(self, *args, **options):
        as_of = options['as_of'] or datetime.now(ZoneInfo(settings.BUSINESS_TIME_ZONE)).date()
        start = options['report_start'] or as_of.replace(month=1, day=1)
        if start > as_of:
            raise CommandError('invalid_report_horizon')
        if connection.vendor == 'postgresql' and connection.in_atomic_block:
            raise CommandError('comparison_requires_top_level_transaction')
        with connection.execute_wrapper(read_only), transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            with pinned():
                before_state = FXSyncState.objects.filter(pk=1).values('release_id', 'seq', 'history_epoch').first()
                business = [{'kind': model._meta.model_name, 'record_id': str(obj.pk), 'business_hash': business_hash(obj)}
                            for model in (Property, Tenant, Transaction, DepositMovement, Property_capital_structure, Lease_rent)
                            for obj in model.objects.order_by('pk')]
                records = []
                for kind, obj, valued_on, currency in comparison_rows(as_of):
                    for target, _ in CURRENCY_CHOICES:
                        result = {'kind': kind, 'record_id': str(obj.pk), 'business_hash': business_hash(obj),
                                  'date': valued_on.isoformat(), 'currency': currency, 'target_currency': target}
                        mirror_effective_date = None
                        for resolver in ('legacy', 'mirror'):
                            try:
                                with calculation_context(resolver):
                                    resolved = get_rate(currency, target, valued_on)
                                    multiplier = resolved['FX']
                                    if resolver == 'mirror':
                                        mirror_effective_date = resolved['effective_date']
                                result[f'{resolver}_multiplier'] = str(multiplier)
                                result[f'{resolver}_error'] = None
                            except (ValueError, LookupError, nx.NetworkXException):
                                result[f'{resolver}_multiplier'] = None
                                result[f'{resolver}_error'] = 'missing_fx'
                        result['multiplier_difference_cause'] = multiplier_difference_cause(result['legacy_multiplier'], result['mirror_multiplier'])
                        if is_rub_fiat_cross(currency, target):
                            result['fix_time_inputs'] = fix_time_inputs(currency, target, mirror_effective_date)
                            if result['multiplier_difference_cause'] == 'canonical_reference_policy':
                                result['multiplier_difference_cause'] = 'unseparated_reference_policy_and_fix_time'
                        result['applicable_behavioral_causes'] = behavioral_causes(kind, obj, currency, target)
                        records.append(result)
                reports, coverage = build_reports(as_of, start, options['report_currency'])
                after_business = [{'kind': model._meta.model_name, 'record_id': str(obj.pk), 'business_hash': business_hash(obj)}
                                  for model in (Property, Tenant, Transaction, DepositMovement, Property_capital_structure, Lease_rent)
                                  for obj in model.objects.order_by('pk')]
                if business != after_business:
                    raise CommandError('business_changed_during_comparison')
                after_state = FXSyncState.objects.filter(pk=1).values('release_id', 'seq', 'history_epoch').first()
                if before_state != after_state:
                    raise CommandError('fx_release_changed_during_comparison')
                output = {'schema_version': 2, 'header': {'generated_at': datetime.now(timezone.utc).isoformat()},
                          'provenance': {'source_commit': options['source_commit'] or None, 'image_digest': options['image_digest'] or None},
                          'horizon': {'as_of': as_of.isoformat(), 'report_start': start.isoformat(), 'report_currency': options['report_currency']},
                          'backend_settings': {'configured_backend': backend(), 'business_time_zone': settings.BUSINESS_TIME_ZONE,
                                               'resolvers': ['legacy', 'mirror'], 'counterfactual_order': ['canonical_reference_policy', 'rent_total_face_value', 'scheduler_rent_denomination', 'scheduler_rent_selection', 'native_stats_and_pnl']},
                          'release': before_state, 'business_records': business,
                          'behavioral_differences': BEHAVIORAL_DIFFERENCES, 'records': records,
                          'report_scope': report_scope(), 'report_families': list(FAMILIES), 'report_coverage': coverage, 'reports': reports}
        # O_NOFOLLOW prevents an output symlink from redirecting private evidence.
        fd = os.open(options['output'], os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(output, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
        self.stdout.write('FX comparison exported')
