import asyncio
import json
from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from rentals.services.fx_context import BEHAVIORS, backend, behavior, calculation_context

DAY = date(2026, 1, 5)


@pytest.fixture
def comparison_case(db):
    from rentals.models import FX, FXAnchor, FXSyncState
    from rentals.tests.factories import PropertyFactory, TenantFactory, TransactionFactory, LeaseRentFactory
    prop = PropertyFactory(currency='USD')
    tenant = TenantFactory(property=prop, lease_start=date(2026, 1, 1), payday=1)
    LeaseRentFactory(tenant=tenant, date_rent_set=tenant.lease_start, currency='EUR', rent=Decimal('100'))
    LeaseRentFactory(tenant=tenant, date_rent_set=tenant.lease_start, currency='EUR', rent=Decimal('150'))
    TransactionFactory(property=prop, tenant=tenant, date=DAY, category='rent', type='income', currency='EUR', amount=Decimal('10'))
    TransactionFactory(property=prop, tenant=tenant, date=DAY, category='rent', type='income', currency='USD', amount=Decimal('5'))
    FXSyncState.objects.create(pk=1, release_id='r1', seq=1, history_epoch=1)
    for day in (tenant.lease_start, DAY):
        for currency, value in [('USD', '1'), ('EUR', '0.5')]:
            FXAnchor.objects.create(date=day, currency=currency, value=value, snapshot_id='s', observation_date=day)
    FX.objects.create(date=tenant.lease_start, from_currency='EUR', to_currency='USD', rate=Decimal('2'))
    return prop, tenant


def export(tmp_path):
    path = tmp_path / 'comparison.json'
    call_command('export_fx_comparison', output=str(path), as_of=DAY, report_start=date(2026, 1, 1), source_commit='a'*40, image_digest='sha256:'+'b'*64)
    return path, json.loads(path.read_text())


@pytest.mark.django_db(transaction=True)
def test_live_reports_counterfactuals_private_deterministic_and_read_only(comparison_case, tmp_path):
    prop, tenant = comparison_case
    with CaptureQueriesContext(connection) as queries:
        path, result = export(tmp_path)
    assert not any(q['sql'].lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'} for q in queries)
    assert path.stat().st_mode & 0o777 == 0o600
    reports = {r['name']: r for r in result['reports']}
    assert all(not r['error'] for r in reports.values()), [(r['name'], r['error']) for r in reports.values() if r['error']]
    rent = reports['tenant_rent.total']
    debt = reports['tenant_debt_standard.balance']
    assert Decimal(rent['legacy']) == 15 and Decimal(rent['mirror']) == 25
    assert Decimal(debt['legacy']) == -85 and Decimal(debt['mirror']) == -275
    causes = {a['cause']: Decimal(a['difference']) for a in debt['attributions']}
    assert causes['rent_total_face_value'] == 10
    assert causes['scheduler_rent_denomination'] == -100
    assert causes['scheduler_rent_selection'] == -100
    assert Decimal(reports['property_native_stats.gross_income_all_time']['mirror']) == 25
    assert Decimal(reports['pnl_native.rent_all_time']['mirror']) == 25
    for resolver in ('legacy', 'mirror'):
        with calculation_context(resolver):
            assert Decimal(rent[resolver]) == tenant.rent_total(DAY, date(2026, 1, 1))
            assert Decimal(debt[resolver]) == tenant.debt(DAY)
            assert Decimal(reports['tenant_debt_advance.balance'][resolver]) == tenant.debt_advance_payment(DAY)
    assert result['provenance']['source_commit'] == 'a'*40
    assert all(r['record_id'] for r in result['records'])
    _, second = export(tmp_path)
    del result['header'], second['header']
    assert result == second


@pytest.mark.django_db(transaction=True)
def test_missing_coverage_is_typed_and_no_private_exception(comparison_case, tmp_path):
    from rentals.models import FXAnchor
    FXAnchor.objects.all().delete()
    _, result = export(tmp_path)
    assert any(r['error'] for r in result['reports'])
    assert any(r['mirror_error'] == 'missing_fx' for r in result['records'])
    assert all(set(r['error'].values()) <= {'missing_fx', 'report_calculation_error'} for r in result['reports'] if r['error'])


def test_nested_and_concurrent_context_isolation(settings):
    settings.FX_BACKEND = 'legacy'
    async def worker(resolver):
        with calculation_context(resolver):
            await asyncio.sleep(0)
            assert backend() == resolver
            assert behavior(BEHAVIORS[0]) == (resolver == 'mirror')
            with calculation_context('mirror', ()):
                await asyncio.sleep(0)
                assert not behavior(BEHAVIORS[0])
            assert backend() == resolver
        assert backend() == 'legacy'
    async def run():
        await asyncio.gather(worker('legacy'), worker('mirror'))
    asyncio.run(run())
    assert settings.FX_BACKEND == 'legacy'


@pytest.mark.django_db(transaction=True)
def test_export_write_guard_rejects_actual_sql(comparison_case, tmp_path, monkeypatch):
    from django.core.management.base import CommandError
    from rentals.management.commands import export_fx_comparison
    from rentals.models import Tenant
    def writing(*args):
        Tenant.objects.update(first_name='should not persist')
    monkeypatch.setattr(export_fx_comparison, 'build_reports', writing)
    with pytest.raises(CommandError, match='comparison_write_forbidden'):
        export(tmp_path)
    assert not Tenant.objects.filter(first_name='should not persist').exists()


@pytest.mark.django_db
def test_interleaved_real_resolvers_and_preloaded_instances(comparison_case):
    from types import SimpleNamespace
    from rentals.models import FX
    from rentals.services.fx import get_rate, PreloadedConverter
    FX.objects.update(rate=Decimal('3'))
    data = [SimpleNamespace(date=DAY, currency='EUR')]
    with calculation_context('legacy'):
        legacy = PreloadedConverter(data, 'USD')
        assert get_rate('EUR', 'USD', DAY)['FX'] == 3
        with calculation_context('mirror'):
            mirror = PreloadedConverter(data, 'USD')
            assert get_rate('EUR', 'USD', DAY)['FX'] == 2
            assert legacy.convert(Decimal(1), 'EUR', 'USD', DAY) == 3
        assert mirror.convert(Decimal(1), 'EUR', 'USD', DAY) == 2
        assert get_rate('EUR', 'USD', DAY)['FX'] == 3


@pytest.mark.django_db(transaction=True)
def test_original_scope_and_native_reference_invariants(comparison_case, tmp_path):
    from rentals.models import FX
    from rentals.tests.factories import PropertyFactory, TransactionFactory
    prop, tenant = comparison_case
    second = PropertyFactory(currency='EUR')
    expense = TransactionFactory(property=second, date=DAY, type='expense', category='utilities', currency='EUR', amount=Decimal('-2'))
    FX.objects.update(rate=Decimal('3'))
    _, result = export(tmp_path)
    scope = result['report_scope']
    assert scope['owner_user_ids'] == sorted([str(prop.owned_by.user_id), str(second.owned_by.user_id)])
    assert next(p for p in scope['properties'] if p['record_id'] == str(second.pk)) == {
        'record_id': str(second.pk), 'owner_user_id': str(second.owned_by.user_id), 'currency': 'EUR'}
    assert scope['tenants'] == [{'record_id': str(tenant.pk), 'property_id': str(prop.pk),
                                 'lease_start': tenant.lease_start.isoformat(), 'lease_end': None, 'payday': 1}]
    assert len(scope['lease_rents']) == 2
    assert scope['deposits'] == [] and scope['capital'] == []
    tx = next(t for t in scope['transactions'] if t['record_id'] == str(expense.pk))
    from rentals.utils import get_category_name
    assert tx['category_label'] == get_category_name(expense.category)
    assert tx['date'] == DAY.isoformat() and tx['property_id'] == str(second.pk)
    native_families = {'tenant_rent', 'tenant_debt_standard', 'tenant_debt_advance', 'property_native_stats', 'pnl_native'}
    for receipt in result['reports']:
        assert not receipt['error']
        if receipt['family'] in native_families:
            assert Decimal(receipt['stages']['legacy']) == Decimal(receipt['stages']['reference'])
    assert any(Decimal(r['stages']['reference']) != Decimal(r['stages']['legacy']) for r in result['reports'] if r['family'] == 'pnl_converted')
    assert {r['entity_id'] for r in result['reports'] if r['family'] == 'portfolio_analytics'} == set(scope['owner_user_ids'])


@pytest.mark.django_db(transaction=True)
def test_export_original_rate_facts_and_calendar(comparison_case, tmp_path):
    from rentals.management.commands.export_fx_comparison import comparison_rows
    from rentals.models import DepositMovement, Lease_rent
    from rentals.tests.factories import PropertyCapitalStructureFactory
    prop, tenant = comparison_case
    deposit = DepositMovement.objects.create(tenant=tenant, date=DAY, currency='EUR', amount=10, kind='received')
    capital = PropertyCapitalStructureFactory(property=prop, capital_structure_date=DAY)
    _, result = export(tmp_path)
    assert result['report_scope']['deposits'] == [dict(record_id=str(deposit.pk), tenant_id=str(tenant.pk), date=DAY.isoformat(), currency='EUR')]
    assert result['report_scope']['capital'] == [dict(record_id=str(capital.pk), property_id=str(prop.pk), date=DAY.isoformat())]
    from rentals.constants import CURRENCY_CHOICES
    assert {code for code, _ in CURRENCY_CHOICES} == {'USD', 'EUR', 'GBP', 'RUB'}
    tenant.lease_start = date(2024, 1, 30)
    tenant.lease_end = date(2024, 5, 30)
    tenant.payday = 31
    tenant.save()
    tenant.rent_history.all().delete()
    for pk, day in ((1, date(2024, 2, 1)), (9, date(2024, 2, 29)), (10, date(2024, 2, 29)), (11, date(2024, 4, 30)), (12, date(2024, 6, 1))):
        Lease_rent.objects.create(pk=pk, tenant=tenant, date_rent_set=day, currency='EUR', rent=100)
    actual = {(str(obj.pk), when.isoformat()) for kind, obj, when, currency in comparison_rows(date(2024, 5, 31)) if kind == 'lease_due'}
    assert actual == {('10', '2024-02-29'), ('10', '2024-03-31'), ('11', '2024-04-30')}


@pytest.mark.django_db
def test_postgresql_export_rejects_nested_transaction(tmp_path):
    from django.core.management.base import CommandError

    if connection.vendor != 'postgresql':
        pytest.skip('PostgreSQL export isolation contract')
    assert connection.in_atomic_block
    output = tmp_path / 'nested.json'
    with pytest.raises(CommandError, match='comparison_requires_top_level_transaction'):
        call_command('export_fx_comparison', output=str(output))
    assert not output.exists()
