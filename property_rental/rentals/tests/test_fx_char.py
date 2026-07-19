"""Golden-master characterization tests for ``FX.get_rate``.

``FX.get_rate(source, target, date)`` resolves an exchange rate between
two currencies, walking an undirected graph of the FX table's currency
pairs via networkx Bellman-Ford shortest-path. It is the conversion
engine underneath ``Transaction.financials`` and ``Tenant.rent_total``
and is the thing Task 10 (FX cache) and later tasks must NOT change
observable behavior for.

Task 9 (wide->long schema migration) preserved every pinned value
below by switching the factory from per-pair columns
(``FXFactory(EURUSD=Decimal('1.10'))``) to long rows
(``FXFactory(from_currency='EUR', to_currency='USD',
rate=Decimal('1.10'))``). The pinned values themselves are unchanged.

Approach (golden master): build a tiny deterministic FX dataset, call
``get_rate`` with known inputs, and assert the EXACT value the current
code returns. Expected values were captured by running the test with
placeholders and reading the assertion-failure output.

PINNED QUIRK — the tail inversion (FIXED in Plan B Task 1)
----------------------------------------------------------
The last line of ``get_rate`` used to be ``fx_rate = round(1 / fx_rate, 6)``.
It UNCONDITIONALLY inverted whatever ``fx_rate`` was accumulated to. So:

* Stored ``EURUSD = 1.10`` → ``get_rate('EUR', 'USD', _)['FX']`` returned
  ``0.909091`` (the reciprocal), not ``1.10``.
* Stored ``EURUSD = 1.10`` → ``get_rate('USD', 'EUR', _)['FX']`` returned
  ``1.100000`` (because the hop divided by 1.10, and the tail inverted back).

Plan B Task 1 (2026-07-19) removed the tail inversion. The values below
were re-pinned to the now-correct outputs. Previous values were
reciprocals due to the ``round(1 / fx_rate, 6)`` bug. Golden values
updated 2026-07-19 for FX inversion fix (Plan B Task 1).
"""

from datetime import date
from decimal import Decimal

import networkx.exception
import pytest

from rentals.models import FX
from rentals.tests.factories import FXFactory


# ---------------------------------------------------------------------------
# FX graph builder
# ---------------------------------------------------------------------------
# Long-format FX schema (Task 9): one row per (date, currency pair). The
# graph is fixed: {EUR-USD, GBP-USD, USD-RUB}. We seed one row per pair
# on the same date. The specific rate values are chosen to be easy to
# eyeball when tracing the algorithm.
#
# Graph:
#     EUR ---1.10--- USD ---90.0--- RUB
#                  /
#            1.25
#           /
#        GBP

_AS_OF = date(2024, 1, 15)


def build_fx_graph():
    """Seed the FX table with a small deterministic currency graph.

    Returns the ``as_of`` date the tests should pass to ``get_rate`` so
    the ``date__lte=as_of`` filter selects exactly these rows.
    """
    FXFactory(
        date=date(2024, 1, 10),
        from_currency="EUR", to_currency="USD", rate=Decimal("1.10"),
    )
    FXFactory(
        date=date(2024, 1, 10),
        from_currency="GBP", to_currency="USD", rate=Decimal("1.25"),
    )
    FXFactory(
        date=date(2024, 1, 10),
        from_currency="USD", to_currency="RUB", rate=Decimal("90.00"),
    )
    return _AS_OF


# ---------------------------------------------------------------------------
# Direct pair: EUR -> USD (single hop, pair EUR->USD, source-first)
# ---------------------------------------------------------------------------

def test_get_rate_direct(db):
    as_of = build_fx_graph()
    result = FX.get_rate("EUR", "USD", as_of)
    # Stored EUR->USD=1.10, hop is source-first (row stored as EUR->USD),
    # so it multiplies: 1 * 1.10 = 1.10. The FX.rate DecimalField has
    # decimal_places=10, so the stored value comes back as
    # 1.1000000000 and the product is 1.1000000000.
    # Golden values updated 2026-07-19 for FX inversion fix (Plan B Task 1).
    # Previous value was Decimal('0.909091') — the reciprocal, pinned while
    # the round(1/fx_rate, 6) tail inversion bug was still in get_rate.
    assert result["FX"] == Decimal("1.1000000000")
    assert result["conversions"] == 1


# ---------------------------------------------------------------------------
# Reverse pair: USD -> EUR (single hop, divides instead of multiplies)
# ---------------------------------------------------------------------------

def test_get_rate_reverse(db):
    as_of = build_fx_graph()
    result = FX.get_rate("USD", "EUR", as_of)
    # The hop is reverse of the stored row (row is EUR->USD, query is
    # USD->EUR), so it divides: 1 / 1.10 = 0.9090909090909090909090909091
    # (full Decimal precision since no round() is applied anymore).
    # Golden values updated 2026-07-19 for FX inversion fix (Plan B Task 1).
    # Previous value was Decimal('1.100000') — the hop divided by 1.10 and
    # the round(1/fx_rate, 6) tail inversion bug flipped it back.
    assert result["FX"] == Decimal("0.9090909090909090909090909091")
    assert result["conversions"] == 1


# ---------------------------------------------------------------------------
# Two-hop pair: EUR -> RUB via USD (Bellman-Ford path EUR-USD-RUB)
# ---------------------------------------------------------------------------

def test_get_rate_two_hop(db):
    as_of = build_fx_graph()
    result = FX.get_rate("EUR", "RUB", as_of)
    # Path is EUR -> USD -> RUB. The EUR->USD hop is source-first (row
    # stored as EUR->USD), so it multiplies by 1.10. The USD->RUB hop is
    # also source-first (row stored as USD->RUB), so it multiplies by
    # 90.00. 1 * 1.10 * 90.00 = 99.00 (with DecimalField
    # decimal_places=10 precision: 99.00000000000000000000).
    # Golden values updated 2026-07-19 for FX inversion fix (Plan B Task 1).
    # Previous value was Decimal('0.010101') — round(1/99, 6) from the tail
    # inversion bug.
    assert result["FX"] == Decimal("99.00000000000000000000")
    assert result["conversions"] == 2


# ---------------------------------------------------------------------------
# No path: USD -> JPY (JPY is not in the graph at all)
# ---------------------------------------------------------------------------

def test_get_rate_no_path(db):
    as_of = build_fx_graph()
    # JPY has no row in the seeded FX graph, so it is not a node in the
    # networkx graph. ``nx.shortest_path`` raises
    # ``networkx.exception.NodeNotFound`` and ``get_rate`` does not catch
    # it, so the exception propagates verbatim to the caller. (Pinned:
    # if a later task wraps this in a ValueError or returns None
    # instead, this test will flag the change.)
    with pytest.raises(networkx.exception.NodeNotFound):
        FX.get_rate("USD", "JPY", as_of)
