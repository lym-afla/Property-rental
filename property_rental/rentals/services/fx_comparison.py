"""Read-only numerical receipts built by the application's report paths."""
from decimal import Decimal, localcontext
from types import SimpleNamespace

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.analytics.pnl import profit_and_loss
from rentals.analytics.portfolio import portfolio_summary
from rentals.analytics.tenant import tenant_rent_performance
from rentals.api.views import PropertyViewSet
from rentals.models import DepositMovement, Lease_rent, Property, Property_capital_structure, Tenant, Transaction
from rentals.services.financials import pnl_calc
from rentals.services.fx import MissingFXRate
from rentals.services.fx_context import BEHAVIORS, calculation_context

STAGES = ('legacy', 'reference', *BEHAVIORS)
FAMILIES = ('tenant_rent', 'tenant_debt_standard', 'tenant_debt_advance',
            'property_native_stats', 'pnl_native', 'pnl_converted',
            'portfolio_analytics', 'tenant_analytics', 'pnl_analytics')


def difference(before, after):
    a, b = Decimal(before), Decimal(after)
    low = min(a.as_tuple().exponent, b.as_tuple().exponent)
    high = max(a.adjusted(), b.adjusted())
    with localcontext() as ctx:
        ctx.prec = max(38, high - low + 2)
        return str(b - a)


def numbers(value, prefix=''):
    if isinstance(value, dict):
        for key in sorted(value):
            yield from numbers(value[key], f'{prefix}.{key}' if prefix else str(key))
    elif isinstance(value, (tuple, list)):
        for i, item in enumerate(value):
            yield from numbers(item, f'{prefix}.{i}')
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('Nonfinite report')
        yield prefix, str(number)
    elif value is None:
        raise MissingFXRate('Incomplete report')


def report_jobs(as_of, start, currency):
    for tenant in Tenant.objects.select_related('property__owned_by__user').order_by('pk'):
        native = tenant.property.currency
        yield 'tenant_rent', str(tenant.pk), native, lambda t=tenant: {'total': t.rent_total(as_of, start)}
        yield 'tenant_debt_standard', str(tenant.pk), native, lambda t=tenant: {'balance': t.debt(as_of)}
        yield 'tenant_debt_advance', str(tenant.pk), native, lambda t=tenant: {'balance': t.debt_advance_payment(as_of)}
        def performance(t=tenant):
            filters = AnalyticsFilters(start, as_of, Grain.MONTH, t.property.currency, None, ())
            result = tenant_rent_performance(t.property.owned_by.user, t.pk, filters)
            if result.issues:
                raise MissingFXRate('Incomplete tenant analytics')
            return {'opening_arrears': result.opening_arrears, 'points': [{key: p[key] for key in ('expected', 'received', 'variance', 'cumulative_arrears')} for p in result.points]}
        yield 'tenant_analytics', str(tenant.pk), native, performance
    properties = list(Property.objects.select_related('owned_by__user').order_by('pk'))
    for prop in properties:
        def stats(p=prop):
            view = SimpleNamespace(get_queryset=lambda: [p])
            req = SimpleNamespace(query_params={'as_of': as_of.isoformat(), 'currency': 'native'})
            data = PropertyViewSet.with_stats.__wrapped__(view, req).data[0]
            return {key: data[key] for key in ('gross_income_all_time', 'expenses_all_time', 'net_income_all_time', 'gross_income_ytd', 'expenses_ytd', 'net_income_ytd')}
        yield 'property_native_stats', str(prop.pk), prop.currency, stats
        for native in (True, False):
            target = prop.currency if native else currency
            def pnl(p=prop, target=target, native=native):
                expenses, ytd, total, _ = pnl_calc([p], target, not native, 2, as_of)
                return {'expenses': expenses, 'rent_ytd': ytd, 'rent_all_time': total}
            yield 'pnl_native' if native else 'pnl_converted', str(prop.pk), target, pnl
    users = {p.owned_by.user_id: p.owned_by.user for p in properties}
    for user_id, user in sorted(users.items()):
        def portfolio(u=user):
            result = portfolio_summary(u, AnalyticsFilters(start, as_of, Grain.MONTH, currency, None, ()))
            # Valuation coverage is represented separately by capital record receipts;
            # these are the portfolio's transaction totals, available without valuations.
            return {key: getattr(result, key) for key in ('revenue', 'costs', 'net_income')}
        yield 'portfolio_analytics', str(user_id), currency, portfolio
        def pnl_analytics(u=user):
            result = profit_and_loss(u, as_of, currency)
            return {key: getattr(result, key) for key in ('total_revenue', 'total_expenses', 'net_income')}
        yield 'pnl_analytics', str(user_id), currency, pnl_analytics


def build_reports(as_of, start, currency):
    reports, coverage = [], []
    for family, entity_id, target, calculate in report_jobs(as_of, start, currency):
        identity = {'family': family, 'entity_id': entity_id, 'currency': target}
        coverage_item = identity | {'metrics': []}
        coverage.append(coverage_item)
        stages, errors = {}, {}
        for i, stage in enumerate(STAGES):
            try:
                with calculation_context('legacy' if i == 0 else 'mirror', BEHAVIORS[:max(0, i-1)]):
                    stages[stage] = dict(numbers(calculate()))
            except MissingFXRate:
                errors[stage] = 'missing_fx'
            except Exception:
                # Keep private exception messages out of both files and stdout.
                errors[stage] = 'report_calculation_error'
        if errors:
            reports.append(identity | {'name': family, 'error': errors, 'legacy': None, 'mirror': None, 'stages': {}, 'attributions': []})
            continue
        keys = set(stages['legacy'])
        if any(set(values) != keys for values in stages.values()) or not keys:
            reports.append(identity | {'name': family, 'error': {'coverage': 'report_shape_changed'}, 'legacy': None, 'mirror': None, 'stages': {}, 'attributions': []})
            continue
        coverage_item['metrics'] = [f'{family}.{key}' for key in sorted(keys)]
        for key in sorted(keys):
            values = {stage: stages[stage][key] for stage in STAGES}
            attributions = []
            for previous, stage in zip(STAGES, STAGES[1:]):
                delta = difference(values[previous], values[stage])
                attributions.append({'cause': 'canonical_reference_policy' if stage == 'reference' else stage,
                                     'from_stage': previous, 'to_stage': stage, 'difference': delta})
            reports.append(identity | {'name': f'{family}.{key}', 'legacy': values['legacy'], 'mirror': values[STAGES[-1]],
                                       'error': None, 'stages': values, 'attributions': attributions, 'unexplained': '0'})
    return reports, coverage


def report_scope():
    """Original scope facts let consumers derive coverage independently of reports."""
    from rentals.utils import get_category_name
    properties = [{'record_id': str(p.pk), 'owner_user_id': str(p.owned_by.user_id), 'currency': p.currency}
                  for p in Property.objects.select_related('owned_by').order_by('pk')]
    return {
        'properties': properties,
        'owner_user_ids': sorted({p['owner_user_id'] for p in properties}),
        'tenants': [{'record_id': str(t.pk), 'property_id': str(t.property_id),
                     'lease_start': t.lease_start.isoformat(),
                     'lease_end': t.lease_end.isoformat() if t.lease_end else None, 'payday': t.payday}
                    for t in Tenant.objects.order_by('pk')],
        'deposits': [{'record_id': str(d.pk), 'tenant_id': str(d.tenant_id),
                      'date': d.date.isoformat(), 'currency': d.currency}
                     for d in DepositMovement.objects.order_by('pk')],
        'capital': [{'record_id': str(c.pk), 'property_id': str(c.property_id),
                     'date': c.capital_structure_date.isoformat()}
                    for c in Property_capital_structure.objects.order_by('pk')],
        'lease_rents': [{'record_id': str(r.pk), 'tenant_id': str(r.tenant_id),
                         'date': r.date_rent_set.isoformat(), 'currency': r.currency}
                        for r in Lease_rent.objects.order_by('pk')],
        'transactions': [{'record_id': str(t.pk), 'property_id': str(t.property_id),
                          'date': t.date.isoformat(), 'currency': t.currency,
                          'type': t.type, 'category': t.category,
                          'category_label': get_category_name(t.category)}
                         for t in Transaction.objects.order_by('pk')],
    }
