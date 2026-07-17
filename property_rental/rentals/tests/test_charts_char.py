"""Golden-master characterization tests for ``rentals.views.get_chart_data``.

``get_chart_data(type, element_id, frequency, from_date, to_date, currency,
properties=None)`` is the chart-dataset builder consumed by the ``index``,
``handle_element`` (property + tenant branches) and (indirectly)
``property_valuation`` views. It is the function Task 12 (charts service
extraction + property_valuation hardcoded-params fix) must NOT regress.

Approach (golden master): build a small deterministic dataset, call
``get_chart_data`` with known inputs, and assert the EXACT dict the current
code returns. Expected payloads were captured by running the tests with
empty placeholders and reading the assertion-failure output, then pasted
back in verbatim.

DEViations from the brief's prose (the brief warned its prose is
approximate and the source is authoritative):

* The 7th positional argument is ``properties`` (an iterable of Property
  instances), NOT ``landlord``. Verified at ``views.py:871``.
* For ``type='homePage'`` the homePage branch is GATED on a truthy
  ``properties`` argument (``if type == 'homePage' and properties:`` at
  ``views.py:889`` and ``:906``). Passing ``None`` (as the brief's literal
  call suggests) skips the branch entirely and yields an empty ``datasets``
  list — which would defeat the brief's explicit instruction to "build a
  dataset ... so the home chart has multiple datasets and multiple
  periods." So the homePage tests pass ``properties=[property]`` (mirroring
  how the real ``index`` caller at ``views.py:117-124`` invokes it).
* ``element_id`` is IGNORED for ``homePage`` (only the ``properties`` arg
  drives filtering); we pass ``None`` to mirror the real caller.

NOTES on determinism:

* ``get_chart_data`` does NOT read the module global
  ``effective_current_date`` (verified by reading the function body and
  its callees — ``Transaction.financials``, ``Tenant.rent_total``,
  ``Property.property_value`` and ``Property.activity_start_date`` all
  take their reference date as an explicit argument). No monkeypatch of
  the global is needed here (contrast with ``test_financials_char.py``'s
  ``pnl_calc`` test).
* All scenarios are SAME-CURRENCY (USD only). ``FX.get_rate`` short-circuits
  at ``source == target`` (``models.py:526``), so no FX rows are needed and
  the wide-FX-schema quirks pinned in ``test_fx_char.py`` cannot leak in.
"""

from datetime import date
from decimal import Decimal

from rentals.models import Property
from rentals.views import get_chart_data
from rentals.tests.factories import (
    LeaseRentFactory,
    PropertyCapitalStructureFactory,
    PropertyFactory,
    TenantFactory,
    TransactionFactory,
    UserFactory,
)


# ---------------------------------------------------------------------------
# Dataset builder (module-level so it's composable; not a fixture).
# ---------------------------------------------------------------------------
#
# One USD property ("Chart Prop") with:
#   * a single Property_capital_structure row dated 2024-01-01
#     (value=200000, debt=100000) so the 'property' chart has data to
#     interpolate;
#   * one tenant (lease_start 2023-06-01, payday=1, monthly rent $1000);
#   * five rent transactions Jan-Apr 2024 ($1000 each);
#   * four expense transactions across distinct categories (tax, utilities,
#     electricity, management) scattered through Q1/Q2 2024.
#
# The date window used by every test is 2024-01-01 .. 2024-12-31. With
# monthly frequency that yields 12 chart points (Feb-24 .. Jan-25 because
# chart_dates shifts both ends forward by one month for freq='M'); yearly
# yields one chart point (2024); quarterly yields four (Q1-Q4 2024).

def build_chart_scenario():
    """Build a deterministic multi-category USD dataset for chart tests.

    Returns a dict with the property, tenant and landlord handles so tests
    can pass them straight into ``get_chart_data``.
    """
    landlord_user = UserFactory(is_landlord=True)
    landlord = landlord_user.landlord  # auto-created by User.save()
    property_usd = PropertyFactory(
        owned_by=landlord, currency="USD", name="Chart Prop"
    )

    # One capital structure row -> property_value returns (200000, 100000)
    # for every chart date in 2024 (only latest_before exists, no
    # interpolation).
    PropertyCapitalStructureFactory(
        property=property_usd,
        capital_structure_date=date(2024, 1, 1),
        capital_structure_value=Decimal("200000.00"),
        capital_structure_debt=Decimal("100000.00"),
    )

    tenant = TenantFactory(
        property=property_usd,
        first_name="Cara",
        last_name="Chart",
        lease_start=date(2023, 6, 1),
        payday=1,
    )
    LeaseRentFactory(
        tenant=tenant, date_rent_set=date(2023, 6, 1), rent=Decimal("1000.00")
    )

    # Rent (income) — Jan..Apr 2024, $1000 each.
    for month in (1, 2, 3, 4):
        TransactionFactory(
            property=property_usd, tenant=tenant,
            category="rent", currency="USD", amount=Decimal("1000.00"),
            date=date(2024, month, 1),
        )

    # Expenses across distinct categories so homePage produces 5 datasets.
    TransactionFactory(
        property=property_usd,
        category="tax", currency="USD", amount=Decimal("200.00"),
        date=date(2024, 1, 15),
    )
    TransactionFactory(
        property=property_usd,
        category="utilities", currency="USD", amount=Decimal("100.00"),
        date=date(2024, 2, 15),
    )
    TransactionFactory(
        property=property_usd,
        category="electricity", currency="USD", amount=Decimal("50.00"),
        date=date(2024, 3, 15),
    )
    TransactionFactory(
        property=property_usd,
        category="management", currency="USD", amount=Decimal("75.00"),
        date=date(2024, 4, 15),
    )

    return {
        "landlord": landlord,
        "property": property_usd,
        "tenant": tenant,
        "from_date": "2024-01-01",
        "to_date": "2024-12-31",
    }


# ---------------------------------------------------------------------------
# homePage — monthly frequency
# ---------------------------------------------------------------------------

def test_get_chart_data_homepage_monthly(db):
    sc = build_chart_scenario()
    properties = Property.objects.filter(id=sc["property"].id)
    actual = get_chart_data(
        type="homePage",
        element_id=None,
        frequency="M",
        from_date=sc["from_date"],
        to_date=sc["to_date"],
        currency="USD",
        properties=properties,
    )
    # Captured verbatim from current code. Notes on the contract being
    # pinned:
    #   * 12 labels because chart_dates shifts BOTH window ends forward by
    #     one month for freq='M' (window 2024-01-01..2024-12-31 -> labels
    #     Feb-24..Jan-25).
    #   * Each point sums the trailing month (start = d - 1 month). So
    #     'rent' buckets double-count at boundaries (Feb-24 bucket = Jan+Feb
    #     rent = $2000); Apr has only Apr rent ($1000) because May onward
    #     is empty.
    #   * 'tax'/'utilities'/etc. are one-shot (single transaction each) so
    #     they show up in exactly one bucket.
    #   * Decimal-vs-int mixing is intentional: financials() returns
    #     Decimal('0.00')-style sums for non-empty buckets but int 0 for
    #     empty ones (the `or 0` fallback in Transaction.financials).
    #   * Dataset order follows insertion order of the first transaction
    #     in each category (rent<tax<utilities<electricity<management),
    #     which is the SQLite DISTINCT iteration order today. A DB swap
    #     or explicit ordering would change this — pinning surfaces that.
    EXPECTED = {
        'labels': [
            'Feb-24', 'Mar-24', 'Apr-24', 'May-24', 'Jun-24', 'Jul-24',
            'Aug-24', 'Sep-24', 'Oct-24', 'Nov-24', 'Dec-24', 'Jan-25',
        ],
        'datasets': [
            {
                'label': 'rent',
                'data': [
                    Decimal('2000'), Decimal('2000'), Decimal('2000'),
                    Decimal('1000'),
                    0, 0, 0, 0, 0, 0, 0, 0,
                ],
            },
            {
                'label': 'tax',
                'data': [
                    Decimal('200'),
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                ],
            },
            {
                'label': 'utilities',
                'data': [
                    0, Decimal('100'),
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                ],
            },
            {
                'label': 'electricity',
                'data': [
                    0, 0, Decimal('50'),
                    0, 0, 0, 0, 0, 0, 0, 0, 0,
                ],
            },
            {
                'label': 'management',
                'data': [
                    0, 0, 0, Decimal('75'),
                    0, 0, 0, 0, 0, 0, 0, 0,
                ],
            },
        ],
        'currency': '$',
    }
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# homePage — yearly frequency
# ---------------------------------------------------------------------------

def test_get_chart_data_homepage_yearly(db):
    sc = build_chart_scenario()
    properties = Property.objects.filter(id=sc["property"].id)
    actual = get_chart_data(
        type="homePage",
        element_id=None,
        frequency="Y",
        from_date=sc["from_date"],
        to_date=sc["to_date"],
        currency="USD",
        properties=properties,
    )
    # Captured verbatim. freq='Y' yields a single chart point d=2024-01-01
    # (chart_dates replaces both ends with Jan 1 of their year). Each
    # dataset's value is financials(end_date=2024-01-01, start_date=d -
    # 12 months = 2023-01-01). The only rent transaction in
    # 2023-01-01..2024-01-01 is the 2024-01-01 row ($1000); Feb/Apr rents
    # fall outside the window. PINNED VERBATIM; flag if Task 12 changes
    # how the yearly window is computed.
    EXPECTED = {
        'labels': ['2024'],
        'datasets': [
            {'label': 'rent', 'data': [Decimal('1000')]},
            {'label': 'tax', 'data': [0]},
            {'label': 'utilities', 'data': [0]},
            {'label': 'electricity', 'data': [0]},
            {'label': 'management', 'data': [0]},
        ],
        'currency': '$',
    }
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# property — monthly frequency (Debt / Equity datasets, 'k' suffix on currency)
# ---------------------------------------------------------------------------

def test_get_chart_data_property(db):
    sc = build_chart_scenario()
    actual = get_chart_data(
        type="property",
        element_id=sc["property"].id,
        frequency="M",
        from_date=sc["from_date"],
        to_date=sc["to_date"],
        currency="USD",
    )
    # Captured verbatim. The 'property' chart produces two datasets
    # ('Debt' and 'Equity'), each a 12-element monthly series. The single
    # Property_capital_structure row (value=200000, debt=100000) means
    # property_value(d) returns (200000, 100000) for every d, so:
    #   Debt    = round(debt / 1000)            = 100
    #   Equity  = round((value - debt) / 1000)  = round(100000/1000) = 100
    # The currency string gets 'k' appended ('views.py:991'). The
    # Decimal('100') rather than int 100 comes from
    # round(Decimal('100000') / 1000, 0) -> Decimal('100').
    EXPECTED = {
        'labels': [
            'Feb-24', 'Mar-24', 'Apr-24', 'May-24', 'Jun-24', 'Jul-24',
            'Aug-24', 'Sep-24', 'Oct-24', 'Nov-24', 'Dec-24', 'Jan-25',
        ],
        'datasets': [
            {
                'label': 'Debt',
                'data': [Decimal('100')] * 12,
            },
            {
                'label': 'Equity',
                'data': [Decimal('100')] * 12,
            },
        ],
        'currency': '$k',
    }
    assert actual == EXPECTED


# ---------------------------------------------------------------------------
# tenant — quarterly frequency (single unlabeled dataset)
# ---------------------------------------------------------------------------

def test_get_chart_data_tenant(db):
    sc = build_chart_scenario()
    actual = get_chart_data(
        type="tenant",
        element_id=sc["tenant"].id,
        frequency="Q",
        from_date=sc["from_date"],
        to_date=sc["to_date"],
        currency="USD",
    )
    # Captured verbatim. The tenant chart produces a SINGLE dataset with
    # NO 'label' key (a quirk of 'views.py:923' — it initializes only
    # {'data': []}). freq='Q' gives four quarter-end dates (Q1..Q4 24).
    # For non-monthly frequencies rent_total is called with the rolling
    # quarter window. Each quarter's rent:
    #   Q1 24 (d=2024-03-31, start=2024-01-01): Jan+Feb+Mar rent = $3000
    #   Q2 24 (d=2024-06-30, start=2024-04-01): Apr rent only      = $1000
    #   Q3/Q4 24: no rent in window                              = 0
    EXPECTED = {
        'labels': ['Q1 24', 'Q2 24', 'Q3 24', 'Q4 24'],
        'datasets': [
            {'data': [Decimal('3000'), Decimal('1000'), 0, 0]},
        ],
        'currency': '$',
    }
    assert actual == EXPECTED
