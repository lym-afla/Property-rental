"""Service-layer tests for the rentals app.

Task 10 introduced ``rentals/services/fx.py`` — the FX graph cache that
backs ``FX.get_rate``. The single biggest perf win in Phase 1:

Before Task 10, ``FX.get_rate`` rebuilt an ``nx.Graph`` from the FX
table on EVERY call. A chart with 360 data points triggered 360 graph
rebuilds per render.

After Task 10, the graph is built at most once per ``as_of`` date and
cached at module scope in ``rentals.services.fx``. ``FX.save`` /
``FX.delete`` invalidate the cache so it can never go stale.

Task 11 introduced ``rentals/services/financials.py`` — the
financial-aggregation service. ``Transaction.financials`` and
``views.pnl_calc`` are now thin delegates; the duplicated
currency-conversion loop that lived in ``Transaction.financials`` is
replaced by the canonical ``convert_transactions`` helper.

The behavioral safety net for both is the char tests
(``test_fx_char.py``, ``test_fx_migration.py``,
``test_financials_char.py``, ``test_charts_char.py``) which pin the
output values byte-for-byte. The unit tests here cover the
service-specific contracts (cache correctness, FX short-circuit) that
the char tests only cover indirectly.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from rentals.services import fx as fx_service
from rentals.tests.factories import FXFactory


@pytest.mark.django_db
def test_fx_graph_is_cached():
    """``build_graph`` must run at most once across multiple ``get_rate``
    calls that share an ``as_of`` date.

    Setup: seed a small FX graph (the same one used by
    ``test_fx_char.py``). Wrap ``build_graph`` with a spy that delegates
    to the real implementation but counts calls. Three ``get_rate``
    calls with the same ``as_of`` must produce at most one
    ``build_graph`` call — the second and third must hit the cache.
    """
    as_of = date(2024, 1, 15)
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

    # Belt-and-suspenders: a leftover cache entry from a prior test
    # would mask a cache-miss bug. Start from a known-empty cache.
    fx_service.invalidate_cache()

    real_build_graph = fx_service.build_graph
    with patch.object(fx_service, "build_graph", wraps=real_build_graph) as spy:
        fx_service.get_rate("EUR", "USD", as_of=as_of)
        fx_service.get_rate("EUR", "USD", as_of=as_of)
        fx_service.get_rate("GBP", "USD", as_of=as_of)

    assert spy.call_count <= 1, (
        f"graph rebuilt {spy.call_count} times; expected cache hit on "
        f"the 2nd and 3rd get_rate call"
    )


@pytest.mark.django_db
def test_fx_graph_cache_invalidated_on_save():
    """Saving a new ``FX`` row must invalidate the cache so the next
    ``get_rate`` sees the new edge."""
    as_of = date(2024, 1, 15)
    FXFactory(
        date=date(2024, 1, 10),
        from_currency="EUR", to_currency="USD", rate=Decimal("1.10"),
    )

    fx_service.invalidate_cache()
    # Prime the cache.
    fx_service.get_rate("EUR", "USD", as_of=as_of)

    real_build_graph = fx_service.build_graph
    with patch.object(fx_service, "build_graph", wraps=real_build_graph) as spy:
        # Adding a new FX row goes through FX.save() (factory does this),
        # which must invalidate.
        FXFactory(
            date=date(2024, 1, 10),
            from_currency="GBP", to_currency="USD", rate=Decimal("1.25"),
        )
        fx_service.get_rate("GBP", "USD", as_of=as_of)

    assert spy.call_count == 1, (
        f"expected exactly one rebuild after save-then-get_rate; "
        f"got {spy.call_count}"
    )


@pytest.mark.django_db
def test_fx_graph_cache_invalidated_on_delete():
    """Deleting an ``FX`` row must invalidate the cache.

    Seed two pairs that share EUR so deleting one still leaves EUR
    reachable in the graph (``get_rate`` after the delete must not
    raise ``NodeNotFound`` — we are testing the cache contract, not the
    no-path branch).
    """
    as_of = date(2024, 1, 15)
    eur_usd = FXFactory(
        date=date(2024, 1, 10),
        from_currency="EUR", to_currency="USD", rate=Decimal("1.10"),
    )
    FXFactory(
        date=date(2024, 1, 10),
        from_currency="EUR", to_currency="GBP", rate=Decimal("0.90"),
    )

    fx_service.invalidate_cache()
    # Prime the cache.
    fx_service.get_rate("EUR", "USD", as_of=as_of)

    real_build_graph = fx_service.build_graph
    with patch.object(fx_service, "build_graph", wraps=real_build_graph) as spy:
        eur_usd.delete()
        # EUR-GBP still exists so EUR is reachable. The cache was
        # invalidated by ``delete()``, so this must trigger a rebuild.
        fx_service.get_rate("EUR", "GBP", as_of=as_of)

    assert spy.call_count == 1, (
        f"expected exactly one rebuild after delete-then-get_rate; "
        f"got {spy.call_count}"
    )


# ---------------------------------------------------------------------------
# convert_transactions (Task 11) — canonical FX-conversion helper
# ---------------------------------------------------------------------------
#
# The char tests cover the consolidated FX loop indirectly via
# ``Transaction.financials`` (test_financials_char.py) and the chart
# builder (test_charts_char.py). The unit test here covers the
# service-level contract the char tests only cover incidentally:
# same-currency rows MUST skip FX entirely (no graph lookup, no
# ``get_rate`` call). The spy asserts the short-circuit holds even when
# an FX row for the currency pair exists in the DB — the contract is
# per-row, not per-DB-state.


@pytest.mark.django_db
def test_convert_transactions_same_currency_skips_fx(sample_property):
    """``convert_transactions`` must skip FX entirely for same-currency rows.

    Two USD transactions on a USD target. The canonical helper must:
    1. Return ``amount_1 + amount_2`` (a plain sum, no rate applied).
    2. NOT touch the FX graph — ``services.fx.get_rate`` must not be
       called. Spied at the ``services.fx.get_rate`` boundary so a
       future regression that swaps the short-circuit for an unconditional
       ``get_rate`` call (which would still return ``{'FX': 1}`` for
       ``source == target`` and accidentally pass the value check) is
       caught.
    """
    from datetime import date as _date
    from unittest.mock import patch as _patch

    from rentals.services import financials as financials_service
    from rentals.services import fx as fx_service
    from rentals.tests.factories import TransactionFactory

    txns = [
        TransactionFactory(
            property=sample_property,
            amount=Decimal("100.00"),
            currency="USD",
            date=_date(2024, 1, 15),
        ),
        TransactionFactory(
            property=sample_property,
            amount=Decimal("200.00"),
            currency="USD",
            date=_date(2024, 2, 15),
        ),
    ]

    # Spy on the FX graph lookup. ``convert_transactions`` -> ``fx.convert``
    # -> ``fx.get_rate`` only when currencies differ; same-currency rows
    # short-circuit in ``fx.convert`` before ``get_rate`` is touched.
    with _patch.object(fx_service, "get_rate", wraps=fx_service.get_rate) as spy:
        total = financials_service.convert_transactions(
            txns, "USD", _date(2024, 3, 1)
        )

    # Plain sum, no rate applied (the short-circuit returns the amount
    # unchanged, so the result keeps the Decimal type from the field).
    assert total == Decimal("300.00")
    assert spy.call_count == 0, (
        f"same-currency rows must skip FX; get_rate was called "
        f"{spy.call_count} time(s)"
    )
