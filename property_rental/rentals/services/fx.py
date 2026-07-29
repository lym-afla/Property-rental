"""FX service layer — currency graph cache and conversion engine.

Task 10 (Phase 1 Foundation). Before this module existed, ``FX.get_rate``
rebuilt an ``nx.Graph`` from the FX table on EVERY call. A chart with
360 data points triggered 360 graph rebuilds per render. This module
caches the graph in Django's cache framework so it is built at most
once per ``as_of`` date, and invalidated whenever an ``FX`` row is
saved or deleted via ``post_save`` / ``post_delete`` signals (Phase 4
Task 3, 2026-07-19).

Public surface (the bits ``FX`` model and callers reach for):

* ``get_rate(from_currency, to_currency, as_of)`` — moved from
  ``FX.get_rate`` (Bellman-Ford shortest-path traversal and the dict
  return shape are preserved; the unconditional tail inversion that
  lived there in Phase 1 was REMOVED in Plan B Task 1, 2026-07-19).
  Characterization tests in ``test_fx_char.py`` /
  ``test_fx_migration.py`` pin the now-correct values.
* ``convert(amount, from_currency, to_currency, as_of)`` — convenience
  wrapper that returns the input unchanged when the currencies match
  and otherwise multiplies by ``get_rate(...)['FX']``.
* ``build_graph(as_of)`` — the raw graph construction (one
  ``date__lte=as_of`` query + ``add_edge`` per row). Exposed as a
  separate function so the cache test can wrap it with a spy.
* ``invalidate_cache()`` — clears the cached graph. Called by the
  ``post_save`` / ``post_delete`` signal handlers in
  ``rentals.signals`` so the cache can never go stale.
* ``update_rates(property_id)`` — the yfinance back-fill routine,
  moved verbatim from ``FX.update_fx_rates``.

Behavior preservation
---------------------
The body of ``get_rate`` below is the body of the old
``FX.get_rate`` (Task 9 long-schema version) with TWO changes: the
inline ``nx.Graph()`` build loop is replaced by ``_get_graph(as_of)``,
and the tail inversion (``fx_rate = round(1 / fx_rate, 6)``) was
REMOVED in Plan B Task 1 (2026-07-19). The Bellman-Ford traversal, the
per-hop ``date__lte`` rate lookup, the multiplication / division per
row direction, and the dict return shape are preserved verbatim. Do
not "improve" any of them — ``test_fx_char.py`` and
``test_fx_migration.py`` will flag a change.
"""

import logging

import networkx as nx
from django.core.cache import cache
from django.db.models import Q

# ``FX`` / ``Property`` / ``update_FX_database`` are imported lazily
# inside the functions that need them. Importing at module scope would
# create a circular import: ``rentals.models`` imports this module
# (``FX.get_rate`` delegates here), and ``rentals.utils`` (imported by
# ``rentals.models``) does the yfinance fetch.

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FX graph cache (Django cache framework)
# ---------------------------------------------------------------------------
#
# Phase 4 Task 3 (2026-07-19) replaced the previous module-level dict
# cache with Django's cache framework. The cache is keyed by the
# ``as_of`` date (the only thing the graph depends on, since the graph
# query is ``date__lte=as_of``). Invalidation now happens via Django
# ``post_save`` / ``post_delete`` signal handlers in ``rentals.signals``
# instead of ``FX.save`` / ``FX.delete`` overrides on the model — the
# override pattern missed writes that bypass ``save()`` (e.g.
# ``QuerySet.update()``) and was an architectural smell. Signals catch
# every ORM-driven write to the FX table.
#
# ``invalidate_cache()`` calls ``cache.clear()`` which is the simplest
# approach for the default ``LocMemCache``. If the cache backend is
# later switched to Redis / memcached, swap to a version-counter pattern
# (key the graph by ``(as_of, fx_version)`` and bump ``fx_version`` on
# invalidation) to avoid clearing unrelated cache keys.
_CACHE_PREFIX = 'fx_graph:'
_CACHE_TIMEOUT = 3600  # 1 hour


# ---------------------------------------------------------------------------
# FX graph cache helpers
# ---------------------------------------------------------------------------
#
# Keyed by ``as_of`` (the only thing the graph depends on, since the
# graph query is ``date__lte=as_of``). ``_get_graph`` looks up the
# Django cache by ``as_of`` date string and rebuilds on a miss. The
# multi-date case (e.g. a back-dated batch job) just triggers one
# rebuild per date, which is correct (each date gets its own key and
# is never reused with stale data) and bounded by the number of dates.


def build_graph(as_of):
    """Construct a fresh ``nx.Graph`` from every FX row on or before
    ``as_of``.

    Each long-format ``FX`` row defines one undirected edge between its
    ``from_currency`` and ``to_currency`` at its ``date``. We only
    consider rows on or before ``as_of`` (same ``date__lte`` filter as
    the wide schema). Edge direction is irrelevant because the old code
    built an undirected ``nx.Graph``; only the pair's membership and
    stored weight matter.

    The ``weight`` is stored on the edge for future use (e.g.
    rate-weighted path selection) but is NOT consulted by ``get_rate``:
    ``nx.shortest_path`` is called without ``weight=``, so path
    selection uses hop-count, matching the wide-schema behavior.
    """
    from rentals.models import FX

    g = nx.Graph()
    for fx in FX.objects.filter(date__lte=as_of):
        if fx.from_currency and fx.to_currency and fx.rate is not None:
            g.add_edge(fx.from_currency, fx.to_currency, weight=float(fx.rate))
    return g


def _get_graph(as_of):
    """Return the cached graph for ``as_of``, rebuilding on a miss.

    Looks the graph up in Django's cache by ``as_of.isoformat()``. On a
    miss, builds the graph and stores it under the same key with the
    configured timeout. The cache key includes the date so two callers
    using different ``as_of`` values never collide.
    """
    key = f'{_CACHE_PREFIX}{as_of.isoformat()}'
    graph = cache.get(key)
    if graph is None:
        graph = build_graph(as_of)
        cache.set(key, graph, _CACHE_TIMEOUT)
    return graph


def invalidate_cache():
    """Clear the FX graph cache.

    Called by the ``post_save`` / ``post_delete`` signal handlers in
    ``rentals.signals`` so the cache can never go stale: any FX write
    or delete forces the next ``get_rate`` to rebuild.
    """
    # ``cache.clear()`` is the simplest approach for LocMemCache (the
    # default and what the test suite uses). For a shared backend
    # (Redis/memcached) this also clears unrelated keys, which is
    # acceptable for a small personal app; if the app grows, swap to a
    # version-counter pattern (see the module docstring).
    cache.clear()


def get_rate(from_currency, to_currency, as_of):
    """Resolve an FX rate between two currencies as of ``as_of``.

    Body moved VERBATIM from ``FX.get_rate`` (Task 9 long-schema
    version) with TWO deliberate changes:

    1. The graph build: the old method built ``nx.Graph()`` inline;
       this service function calls ``_get_graph(as_of)`` to hit the
       cache.
    2. The tail inversion (``fx_rate = round(1 / fx_rate, 6)``) was
       REMOVED in Plan B Task 1 (2026-07-19). It was a latent bug that
       unconditionally returned the reciprocal of the accumulated path
       rate. The double-cancel in the chart math hid it in production,
       but the new Currency Exposure chart (Plan C) would have exposed
       it, and the reciprocal is just wrong.

    The Bellman-Ford traversal, per-hop rate lookup, multiply / divide
    logic, and the dict return shape are otherwise unchanged.

    Pinned by ``test_fx_char.py`` and ``test_fx_migration.py`` — any
    drift in the output will fail those tests.
    """
    from rentals.models import FX

    source = from_currency
    target = to_currency
    date = as_of

    fx_rate = 1
    dates_async = False
    dates_list = []

    if source == target:
        return {
            'FX': fx_rate,
            'conversions': 0,
            'dates_async': dates_async,
            'FX dates used': dates_list
        }

    # Cached graph (was: ``nx.Graph()`` + ``FX.objects.filter(date__lte=date)``
    # inline on every call). See ``_get_graph`` for cache semantics.
    g = _get_graph(date)

    # Finding shortest path for cross-currency conversion using
    # "Bellman-Ford" algorithm. Behavior preserved verbatim from the
    # wide schema: raises ``networkx.exception.NodeNotFound`` if the
    # source or target is not in the graph.
    cross_currency = nx.shortest_path(g, source, target, method='bellman-ford')

    # Walk each hop in the chosen path and multiply / divide by the
    # most recent (date__lte=date) FX rate for that pair.
    for i in range(1, len(cross_currency)):
        i_source = cross_currency[i - 1]
        i_target = cross_currency[i]

        # Latest long-format row for the (i_source, i_target) pair on
        # or before ``date``. The pair direction in the row may be
        # either way around (long format is logically undirected
        # because the old graph was), so we accept both orderings.
        fx_call = (
            FX.objects.filter(
                date__lte=date,
                rate__isnull=False,
            )
            .filter(
                Q(from_currency=i_source, to_currency=i_target)
                | Q(from_currency=i_target, to_currency=i_source)
            )
            .order_by('-date')
            .first()
        )

        if not fx_call:
            raise ValueError(
                f"FX rate for {i_source} to {i_target} not found."
            )

        # If the stored row is in the i_source->i_target direction we
        # multiply (same as ``element.find(i_source) == 0`` in the
        # old code); otherwise we divide.
        if fx_call.from_currency == i_source and fx_call.to_currency == i_target:
            fx_rate *= fx_call.rate
        else:
            fx_rate /= fx_call.rate

        dates_list.append(fx_call.date)
        dates_async = (dates_list[0] != fx_call.date) or dates_async

    # FX inversion bug fixed 2026-07-19: was ``fx_rate = round(1 / fx_rate, 6)``
    # here, which UNCONDITIONALLY inverted every rate (stored EURUSD=1.10 was
    # returned as 0.909091). The bug was hidden in production because the chart
    # math used the rate twice (canceling the inversion), but the new Currency
    # Exposure chart (Plan C) would have surfaced it. Removed in Plan B Task 1.
    return {
        'FX': fx_rate,
        'conversions': len(cross_currency) - 1,
        'dates_async': dates_async,
        'dates': dates_list
    }


def convert(amount, from_currency, to_currency, as_of):
    """Convert ``amount`` from ``from_currency`` to ``to_currency`` as
    of ``as_of``.

    Returns ``amount`` unchanged when the two currencies are equal
    (skips the graph entirely). Otherwise multiplies by
    ``get_rate(...)['FX']``.
    """
    if from_currency == to_currency:
        return amount
    return amount * get_rate(from_currency, to_currency, as_of)['FX']


class PreloadedConverter:
    """Resolve a batch of transaction conversions from one FX-row query.

    The public ``get_rate`` function deliberately retains its legacy
    query-per-hop behavior. Analytics needs the same graph/path/rate semantics
    for many rows, so this resolver preloads every potentially relevant FX row
    once and performs the identical dated graph traversal in memory.
    """

    def __init__(self, transactions, target_currency):
        self.target_currency = target_currency
        cross_currency_dates = [
            transaction.date
            for transaction in transactions
            if transaction.currency != target_currency
        ]
        self._rows = ()
        self._graphs = {}
        if cross_currency_dates:
            from rentals.models import FX

            self._rows = tuple(
                FX.objects.filter(
                    date__lte=max(cross_currency_dates), rate__isnull=False
                )
            )

    def _graph(self, as_of):
        graph = self._graphs.get(as_of)
        if graph is not None:
            return graph

        graph = nx.Graph()
        for fx in self._rows:
            if fx.date <= as_of:
                graph.add_edge(
                    fx.from_currency, fx.to_currency, weight=float(fx.rate)
                )
        self._graphs[as_of] = graph
        return graph

    def _latest_rate(self, source, target, as_of):
        matches = [
            fx
            for fx in self._rows
            if fx.date <= as_of
            and (
                (fx.from_currency == source and fx.to_currency == target)
                or (fx.from_currency == target and fx.to_currency == source)
            )
        ]
        if not matches:
            raise ValueError(f"FX rate for {source} to {target} not found.")
        return max(matches, key=lambda fx: fx.date)

    def convert(self, amount, from_currency, to_currency, as_of):
        if from_currency == to_currency:
            return amount

        cross_currency = nx.shortest_path(
            self._graph(as_of), from_currency, to_currency, method="bellman-ford"
        )
        fx_rate = 1
        for index in range(1, len(cross_currency)):
            source = cross_currency[index - 1]
            target = cross_currency[index]
            fx = self._latest_rate(source, target, as_of)
            if fx.from_currency == source and fx.to_currency == target:
                fx_rate *= fx.rate
            else:
                fx_rate /= fx.rate
        return amount * fx_rate


def preload_converter(transactions, target_currency):
    """Return an FX converter that needs at most one FX-row query for a batch."""
    return PreloadedConverter(transactions, target_currency)


def update_rates(property_id):
    """Back-fill FX rates for a property's transaction dates via
    yfinance. Body moved VERBATIM from ``FX.update_fx_rates`` (Task 9
    long-schema version) — only the surrounding ``FX`` reference is
    re-resolved locally (lazy import to avoid a module-load circular
    import with ``rentals.models``).
    """
    from rentals.models import FX, Property
    from rentals.utils import update_FX_database

    # Long format: the pairs that need to be fetched are still
    # hard-coded here (the same three pairs as before) — a future task
    # can revisit. The pair list mirrors the legacy per-pair columns
    # (EURUSD, GBPUSD, USDRUB) so behavior is unchanged.
    currency_pairs = [("EUR", "USD"), ("GBP", "USD"), ("USD", "RUB")]

    # Get the specific property
    property_instance = Property.objects.get(id=property_id)

    # Scan Transaction instances in the database to collect dates
    transaction_dates = property_instance.transactions.values_list('date', flat=True)

    logger.info("Checking FX rates for %s dates", len(transaction_dates))
    count = 0
    for date in transaction_dates:
        count += 1
        logger.info("%s of %s", count, len(transaction_dates))
        for source, target in currency_pairs:
            # Check if a long-format FX rate already exists for the
            # (date, pair) combination.
            existing_rate = FX.objects.filter(
                date=date,
                from_currency=source,
                to_currency=target,
            ).first()

            if existing_rate is None or existing_rate.rate is None:
                # Fetch the FX rate for the date.
                rate_data = update_FX_database(source, target, date)

                if rate_data is not None:
                    # Upsert a long-format FX row.
                    FX.objects.update_or_create(
                        date=rate_data['requested_date'],
                        from_currency=source,
                        to_currency=target,
                        defaults={'rate': rate_data['exchange_rate']},
                    )
                    logger.info("%s%s for %s is updated", source, target, rate_data["requested_date"])
                else:
                    raise Exception(f'{source}{target} for {date} is NOT updated. Yahoo Finance is not responding correctly')
            else:
                logger.info("%s%s for %s already exists", source, target, date)
