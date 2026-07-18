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

PINNED QUIRK — the tail inversion
---------------------------------
The last line of ``get_rate`` is ``fx_rate = round(1 / fx_rate, 6)``. It
UNCONDITIONALLY inverts whatever ``fx_rate`` was accumulated to. So:

* Stored ``EURUSD = 1.10`` → ``get_rate('EUR', 'USD', _)['FX']`` returns
  ``0.909091`` (the reciprocal), not ``1.100000``.
* Stored ``EURUSD = 1.10`` → ``get_rate('USD', 'EUR', _)['FX']`` returns
  ``1.100000`` (because the hop divides by 1.10, and the tail inverts
  back).

This is a latent bug: the function effectively swaps "direct" and
"reverse" semantics. We PIN IT VERBATIM here — do not "fix" it in this
test. Task 9 will decide whether to preserve or correct the behavior;
until then this characterization is the safety net.
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
    # PINNED QUIRK: stored EUR->USD=1.10, but get_rate returns the
    # reciprocal (round(1/1.10, 6) = 0.909091) because of the tail
    # inversion. See module docstring.
    assert result["FX"] == Decimal("0.909091")
    assert result["conversions"] == 1


# ---------------------------------------------------------------------------
# Reverse pair: USD -> EUR (single hop, divides instead of multiplies)
# ---------------------------------------------------------------------------

def test_get_rate_reverse(db):
    as_of = build_fx_graph()
    result = FX.get_rate("USD", "EUR", as_of)
    # PINNED QUIRK: the hop computes 1 / 1.10, then the tail inversion
    # flips it back to 1.100000. So the "reverse" pair actually returns
    # the stored value. See module docstring.
    assert result["FX"] == Decimal("1.100000")
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
    # 90.00. 1 * 1.10 * 90.00 = 99.00. Tail inversion:
    # round(1/99, 6) = 0.010101.
    assert result["FX"] == Decimal("0.010101")
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
