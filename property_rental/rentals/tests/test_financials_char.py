"""Golden-master characterization tests for the rental financials.

The five methods pinned here are the ones that later tasks (service
extraction in Task 5, FX cache in Task 11, FX wide->long schema migration
in Task 9) must NOT change observable behavior for:

* ``Tenant.rent_total``
* ``Tenant.debt``
* ``Tenant.debt_advance_payment``
* ``Transaction.financials`` (classmethod)
* ``pnl_calc`` (module-level function in ``rentals.views``)

Approach (golden master): build a tiny deterministic dataset, call the
method with known inputs, and assert the EXACT value the current code
returns. The expected values were captured by running with placeholders
and reading the assertion-failure output. If a future task regresses any
of these, the test fails loudly.

Conventions:
* Every date and amount is hard-coded. No ``date.today()`` / ``random``
  in scenarios. ``pnl_calc`` is the one place that would normally be
  non-deterministic (it now takes the as-of date as an ``as_of`` keyword
  argument — Task 8 removed the module-global ``effective_current_date``
  it used to read); we pin it to a fixed date by passing ``as_of``
  directly.
* Same-currency paths skip FX entirely; the cross-currency scenario
  exercises the one FX pair that has a real column today (``GBPUSD``).
"""

from datetime import date
from decimal import Decimal

from rentals.models import Transaction
from rentals import views
from rentals.tests.factories import (
    FXFactory,
    LeaseRentFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# Scenario builders (module-level so they're composable; not fixtures).
# Each returns a small bag of the created objects so tests can pass them
# straight into the methods under test.
# ---------------------------------------------------------------------------

def build_arrears_scenario():
    """USD-only property + tenant who is in arrears as of 2024-04-15.

    Lease starts 2024-01-01 with $1000/month rent due on day 1 of each
    month. Only Jan and Feb are paid (Mar is missing) so as of 2024-04-15
    the tenant is behind.
    """
    landlord_user = UserFactory(is_landlord=True)
    landlord = landlord_user.landlord  # auto-created by User.save()
    property_usd = PropertyFactory(owned_by=landlord, currency="USD", name="Arrears Prop")

    tenant = TenantFactory(
        property=property_usd,
        first_name="Anna",
        last_name="Arrears",
        lease_start=date(2024, 1, 1),
        payday=1,
    )
    # Monthly rate $1000 from lease start.
    LeaseRentFactory(tenant=tenant, date_rent_set=date(2024, 1, 1), rent=Decimal("1000.00"))

    # Two rent payments only (Jan + Feb). March is unpaid -> arrears.
    TransactionFactory(
        property=property_usd, tenant=tenant,
        category="rent", currency="USD", amount=Decimal("1000.00"),
        date=date(2024, 1, 1),
    )
    TransactionFactory(
        property=property_usd, tenant=tenant,
        category="rent", currency="USD", amount=Decimal("1000.00"),
        date=date(2024, 2, 1),
    )
    return {
        "landlord": landlord,
        "property": property_usd,
        "tenant": tenant,
        "as_of": date(2024, 4, 15),
    }


def build_cross_currency_scenario():
    """GBP property + GBP rent transactions, summed to USD via FX.

    The code path inside ``Tenant.rent_total`` only takes the FX branch
    when ``property.currency != target_currency``. So to exercise the
    actual conversion (and the ``GBPUSD`` FX column) the property itself
    must be denominated in GBP, with target_currency='USD'.
    """
    landlord_user = UserFactory(is_landlord=True)
    landlord = landlord_user.landlord
    property_gbp = PropertyFactory(owned_by=landlord, currency="GBP", name="GBP Prop")

    tenant = TenantFactory(
        property=property_gbp,
        first_name="Greg",
        last_name="Sterling",
        lease_start=date(2024, 1, 1),
        payday=1,
    )

    # Fixed GBP->USD rate for the conversion window (long format, Task 9:
    # one row per currency pair instead of a per-pair column).
    FXFactory(
        date=date(2024, 1, 1),
        from_currency="GBP", to_currency="USD", rate=Decimal("1.25"),
    )

    # Two GBP rent transactions of GBP 100 each.
    TransactionFactory(
        property=property_gbp, tenant=tenant,
        category="rent", currency="GBP", amount=Decimal("100.00"),
        date=date(2024, 1, 15),
    )
    TransactionFactory(
        property=property_gbp, tenant=tenant,
        category="rent", currency="GBP", amount=Decimal("100.00"),
        date=date(2024, 2, 15),
    )
    return {
        "landlord": landlord,
        "property": property_gbp,
        "tenant": tenant,
        "fx_date": date(2024, 1, 1),
    }


def build_financials_scenario():
    """Property with mixed income + expense transactions for financials().

    USD property with one income ('rent') and one expense ('tax') so
    ``Transaction.financials`` has both transaction_type filters to chew on.
    """
    landlord_user = UserFactory(is_landlord=True)
    landlord = landlord_user.landlord
    property_usd = PropertyFactory(owned_by=landlord, currency="USD", name="Financials Prop")

    TransactionFactory(
        property=property_usd,
        category="rent", currency="USD", amount=Decimal("500.00"),
        date=date(2024, 3, 1),
    )
    TransactionFactory(
        property=property_usd,
        category="tax", currency="USD", amount=Decimal("200.00"),
        date=date(2024, 3, 15),
    )
    return {
        "landlord": landlord,
        "property": property_usd,
    }


# ---------------------------------------------------------------------------
# Tenant.debt
# ---------------------------------------------------------------------------

def test_tenant_debt_arrears_scenario(db):
    sc = build_arrears_scenario()
    actual = sc["tenant"].debt(sc["as_of"])
    # As of 2024-04-15 the tenant owes rent for Jan, Feb, Mar, Apr (4 months
    # x $1000 = $4000 due) and has paid only Jan + Feb ($2000). debt is
    # paid - due = -2000 (negative == tenant is in arrears).
    EXPECTED = Decimal("-2000.00")
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# Tenant.debt_advance_payment
# ---------------------------------------------------------------------------

def test_tenant_debt_advance_payment_scenario(db):
    sc = build_arrears_scenario()
    actual = sc["tenant"].debt_advance_payment(sc["as_of"])
    # Completed months Jan/Feb/Mar accrue ($3000) plus the current month
    # (Apr) accrues because 2024-04-15 is >= 7 days past the Apr-1 payday
    # ($1000) -> $4000 due. Paid = $2000. debt = paid - due = -2000.
    EXPECTED = Decimal("-2000.00")
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# Tenant.rent_total — same currency (USD -> USD, no FX)
# ---------------------------------------------------------------------------

def test_tenant_rent_total_same_currency(db):
    sc = build_arrears_scenario()
    actual = sc["tenant"].rent_total(
        end_date=sc["as_of"],
        start_date=sc["tenant"].lease_start,
    )
    # Two USD rent transactions of $1000 each, target currency matches
    # property currency so the aggregate(Sum) path runs (no FX).
    EXPECTED = Decimal("2000")
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# Tenant.rent_total — cross currency (GBP -> USD via GBPUSD column)
# ---------------------------------------------------------------------------

def test_tenant_rent_total_cross_currency(db):
    sc = build_cross_currency_scenario()
    actual = sc["tenant"].rent_total(
        end_date=date(2024, 12, 31),
        start_date=sc["tenant"].lease_start,
        target_currency="USD",
    )
    # Two GBP 100 rent payments on a GBP property, summed to USD. With the
    # FX inversion bug fixed (Plan B Task 1, 2026-07-19),
    # FX.get_rate('GBP', 'USD', date) now returns the stored GBPUSD=1.25
    # (the hop is source-first, so it multiplies; previously the tail
    # inversion ``round(1/1.25, 6)`` returned 0.800000). So
    # 100.00 * 1.2500000000 * 2 = 250.000000000000 (the 12 decimals come
    # from amount(2dp) * rate(10dp) summed across 2 rows).
    # Golden values updated 2026-07-19 for FX inversion fix (Plan B Task 1).
    # Previous value was Decimal('160.00000000') — based on the reciprocal
    # rate 0.800000.
    EXPECTED = Decimal("250.000000000000")
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# Transaction.financials (classmethod) — aggregation with FX conversion
# ---------------------------------------------------------------------------

def test_transaction_financials_aggregation(db):
    sc = build_financials_scenario()
    # target_currency = 'USD' matches all rows so FX.get_rate short-circuits
    # (source == target); we still pass target_currency because the method
    # raises ValueError otherwise.
    actual = Transaction.financials(
        end_date=date(2024, 12, 31),
        target_currency="USD",
        properties=[sc["property"]],
    )
    # Both rows (rent $500 + tax $200) are USD; FX.get_rate('USD', 'USD',
    # _) returns 1. Sum = 700.00.
    EXPECTED = Decimal("700.00")
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# pnl_calc — module function in rentals.views
#
# NB: ``pnl_calc`` takes the as-of date as an ``as_of`` keyword argument
# (Task 8 replaced the read of the module-global ``effective_current_date``
# with a per-user ``User.effective_date`` field and threaded the date
# through as a parameter). The characterization test pins it to a fixed
# date by passing ``as_of`` directly — no monkeypatch required.
# ---------------------------------------------------------------------------

def test_pnl_calc_portfolio(db):
    fixed_now = date(2024, 4, 15)

    sc = build_financials_scenario()
    properties = [sc["property"]]
    expenses, rent_ytd, rent_all_time, unique_categories = views.pnl_calc(
        properties=properties,
        target_currency="USD",
        default_currency_for_all_data=False,
        digits=2,
        as_of=fixed_now,
    )
    # Captured verbatim from the current code with effective_current_date
    # pinned to 2024-04-15. The 'rent' category is returned bare via
    # aggregate(Sum) (Decimal('500')); the 'tax' expense is rounded to
    # float (200.0) and accumulated into 'total' as a Decimal. The mixed
    # types are part of the contract being pinned.
    EXPECTED_RENT_YTD = Decimal("500")
    EXPECTED_RENT_ALL_TIME = Decimal("500")
    EXPECTED_EXPENSES = {
        "Tax": {"ytd": 200.0, "all_time": 200.0},
        "total": {"ytd": Decimal("200"), "all_time": Decimal("200")},
    }
    EXPECTED_CATEGORIES = ["rent", "tax"]

    assert rent_ytd == EXPECTED_RENT_YTD
    assert rent_all_time == EXPECTED_RENT_ALL_TIME
    assert expenses == EXPECTED_EXPENSES
    assert unique_categories == EXPECTED_CATEGORIES
