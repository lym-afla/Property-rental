"""Financial-aggregation service layer.

Task 11 (Phase 1 Foundation). Moves the financial-aggregation logic
that used to live in two places:

* ``Transaction.financials`` classmethod (``rentals/models.py``) — the
  filtered-sum-with-FX-conversion entry point used by ``index``,
  ``handle_element`` (property branch) and ``get_chart_data``.
* ``pnl_calc`` module function (``rentals/views.py``) — the per-category
  YTD / all-time expense aggregator used by ``index`` and
  ``handle_element``.

Both bodies are moved here VERBATIM. The only structural change is that
the inline FX-conversion loop that appeared in ``Transaction.financials``
(and is duplicated, with slight variations, in ``Tenant.rent_total`` and
``table_data``) is replaced by a call to :func:`convert_transactions`,
the single canonical helper. The characterization tests in
``test_financials_char.py`` and ``test_charts_char.py`` pin the outputs
of both functions byte-for-byte, so any drift in the consolidation
fails loudly.

Public surface:

* :func:`convert_transactions` — sum an iterable of transactions into a
  single ``target_currency`` amount as of ``as_of``. Skips FX entirely
  when ``transaction.currency == target_currency`` (the
  ``services.fx.convert`` short-circuit), otherwise multiplies each row
  by ``services.fx.get_rate(...)['FX']``.
* :func:`aggregate` — body of the old ``Transaction.financials``,
  moved verbatim. Filters by date / properties / tenants / type /
  category and returns the converted sum.
* :func:`pnl_calc` — body of the old ``views.pnl_calc``, moved verbatim.
  Returns ``(expenses, rent_ytd, rent_all_time, unique_categories)``.

Behavior preservation
---------------------
The bodies below are copies of the pre-Task-11 code with two
mechanical changes only:

1. ``Transaction.financials`` used ``queryset.values('date', ...).all()``
   and indexed dicts. ``aggregate`` iterates the queryset directly and
   accesses ``.amount`` / ``.currency`` / ``.date`` as attributes so the
   same :func:`convert_transactions` helper can accept either model
   instances (the brief's unit test) or queryset rows. Field types and
   precision are unchanged (``DecimalField`` returns ``Decimal`` either
   way).
2. The inline FX loop ``fx_rate = FX.get_rate(...)['FX']; total +=
   amount * fx_rate`` is replaced by ``services.fx.convert(amount,
   currency, target_currency, as_of)``. ``services.fx.convert`` returns
   ``amount`` unchanged when the currencies match (skipping the graph
   entirely), and otherwise multiplies by ``get_rate(...)['FX']`` —
   identical arithmetic to the original loop.

Known latent bugs pinned by Task 3 char tests (NOT fixed here):
* ``pnl_calc`` returns mixed numeric types (per-category values are
  ``float`` after ``round(float(...), digits)``; the ``total`` sub-dict
  accumulates raw ``Decimal`` sums). Pinned by
  ``test_pnl_calc_portfolio``.
* ``Transaction.financials`` raises ``ValueError`` when
  ``target_currency`` is None — kept verbatim.
* The commented-out single-property short-circuit in the old
  ``Transaction.financials`` (``FX_conversion_required`` toggle) was
  dead code — the toggle was hard-coded to ``True``. Dropped during the
  move since the live branch is the only one char tests cover; the
  ``FX_conversion_required = True`` constant is preserved as a comment
  below for archeological discoverability.
"""

from datetime import date

from django.db.models import Q, Sum

# ``Transaction``, ``FX``, ``get_category_name`` are imported lazily
# inside the functions that need them. Importing at module scope would
# create a circular import: ``rentals.models`` / ``rentals.utils`` are
# imported by callers (views, models) that this service delegates back
# to, and ``rentals.views`` (which used to host ``pnl_calc``) imports
# ``rentals.models``.


# ---------------------------------------------------------------------------
# convert_transactions — canonical FX-conversion loop
# ---------------------------------------------------------------------------
#
# Consolidates the per-row FX-multiply loops that were duplicated across:
#   * ``Transaction.financials`` (models.py) — now ``aggregate`` below.
#   * ``Tenant.rent_total`` (models.py) — UNCHANGED in this task; the
#     ``rent_total`` loop has a different short-circuit contract
#     (``property.currency == target_currency`` rather than per-row
#     ``transaction.currency == target_currency``) so consolidating it
#     is NOT a mechanical change. Left for a later task.
#   * ``pnl_calc`` (views.py) — also UNCHANGED here; ``pnl_calc`` has
#     the additional ``default_currency_for_all_data`` gate that
#     switches between ``aggregate(Sum)`` and the FX loop, so it is
#     moved verbatim rather than consolidated.
#
# The contract: given an iterable of objects with ``.amount``, ``.currency``
# and ``.date`` attributes, return the sum of (amount converted to
# ``target_currency`` as of ``as_of``) across the iterable. Same-currency
# rows skip FX entirely (the ``services.fx.convert`` short-circuit).
def convert_transactions(transactions, target_currency, as_of):
    """Sum ``transactions`` into ``target_currency`` as of ``as_of``.

    Each row is multiplied by ``services.fx.get_rate(row.currency,
    target_currency, row.date)['FX']`` when the currencies differ, and
    passed through unchanged when they match. Returns a ``Decimal`` (or
    ``int`` 0 for an empty iterable, matching the
    ``Transaction.financials`` ``total_amount = 0`` initializer).
    """
    from rentals.services import fx as fx_service

    total = 0
    for transaction in transactions:
        total += fx_service.convert(
            transaction.amount,
            transaction.currency,
            target_currency,
            transaction.date,
        )
    return total


# ---------------------------------------------------------------------------
# aggregate — body of the old Transaction.financials classmethod
# ---------------------------------------------------------------------------
#
# Moved verbatim from ``rentals/models.py`` (Task 10-era version). The
# class-level docstring is preserved as the function docstring. The
# inline FX loop is replaced by ``convert_transactions``; the ``.values()``
# projection is dropped so ``convert_transactions`` can read attributes
# off the model instance (matching the brief's unit-test call shape).
#
# Latent-bug preservation: the ``FX_conversion_required`` flag in the
# original was hard-coded to ``True`` (the only branch that ran). The
# commented-out single-property short-circuit (``# if properties is not
# None and len(properties) == 1:``) was dead. Both are dropped here; the
# char tests only cover the live branch.
def aggregate(cls, end_date, target_currency=None, properties=None,
              tenants=None, start_date=None, transaction_type=None,
              category=None):
    """Calculate the sum of transactions for a specific period and type.

    Args:
        cls: The Transaction model class (passed by the
            ``Transaction.financials`` delegate).
        end_date: Defines the end date for the observation period.
        target_currency (str): Currency to sum into. Required — ``None``
            raises ``ValueError`` (latent behavior pinned by the char
            tests' call shape).
        properties (iterable): Properties to filter to.
        tenants (iterable): Tenants to filter to.
        start_date: Defines the start date for the observation period.
            All-time if not defined.
        transaction_type (str): 'income' or 'expense'.
        category: Filter by transaction category.

    Returns:
        Decimal: The total sum of transactions in ``target_currency``.
    """
    # ``FX_conversion_required`` was a hard-coded True toggle in the
    # pre-Task-11 body; the only live branch always called FX.get_rate.
    # Preserved as a comment for archeological discoverability — the
    # char tests only cover this branch.
    # FX_conversion_required = True

    queryset = cls.objects.filter(date__lte=end_date)

    if properties is not None:
        queryset = queryset.filter(property__in=properties)

    if tenants is not None:
        queryset = queryset.filter(tenant__in=tenants)

    # Dead-code short-circuit dropped (was commented out in the original;
    # the live branch is the ``target_currency is None`` check below).
    if target_currency is None:
        raise ValueError('Target currency is not defined')

    if start_date:
        queryset = queryset.filter(date__range=(start_date, end_date))

    if transaction_type:
        queryset = queryset.filter(type=transaction_type)

    if category:
        queryset = queryset.filter(category=category)

    # Pre-Task-11 body used ``queryset.values('date', 'currency',
    # 'amount').all()`` and indexed dicts in the loop. We iterate the
    # queryset directly so convert_transactions can read attributes off
    # the model instance — functionally identical output, field types
    # unchanged.
    transactions = queryset.all()

    # Inline FX loop replaced by the canonical helper. ``convert_transactions``
    # multiplies each row by ``services.fx.get_rate(...)['FX']`` when
    # currencies differ and returns the amount unchanged otherwise —
    # identical arithmetic to the original loop.
    total_amount = convert_transactions(transactions, target_currency, end_date)

    return total_amount


# ---------------------------------------------------------------------------
# pnl_calc — body of the old views.pnl_calc module function
# ---------------------------------------------------------------------------
#
# Moved verbatim from ``rentals/views.py`` (Task 8-era signature with the
# ``as_of`` kwarg). The two inline FX loops (YTD and all-time windows
# under the ``default_currency_for_all_data`` branch) are NOT consolidated
# into ``convert_transactions`` in this task: the surrounding code reads
# ``queryset.values('date', 'currency', 'amount')`` and the loop body
# accumulates into a per-category variable that feeds the mixed-type
# contract pinned by ``test_pnl_calc_portfolio``. Consolidating would
# require dropping the ``.values()`` projection and changing the
# accumulation style — that is a behavior-risking change, not a
# mechanical one, so the loops are moved verbatim. A later task can
# consolidate once the per-category mixed-type bug is resolved.
def pnl_calc(properties, target_currency, default_currency_for_all_data,
             digits, as_of=None):
    """Calculate P&L for given properties.

    Signature unchanged from the pre-Task-11 ``views.pnl_calc``: callers
    pass ``as_of`` explicitly (Task 8 removed the module-global
    ``effective_current_date`` the function used to read).
    """
    # ``Transaction``, ``FX``, ``get_category_name`` are imported lazily
    # to avoid a module-load circular import (models imports constants
    # that utils also imports; views imports models; this service is
    # imported by both).
    from rentals.models import FX, Transaction
    from rentals.utils import get_category_name

    # ``as_of`` is the per-user effective date that drives YTD/all-time
    # windowing. Replaces the former read of the process-global
    # ``effective_current_date``. Defaults to ``date.today()`` to keep the
    # function callable without a request context (the characterization
    # test passes a fixed date explicitly).
    if as_of is None:
        as_of = date.today()

    current_year_start = as_of.replace(month=1, day=1)

    # Filter transactions for the specified date range
    # filtered_transactions = element.transactions.filter(
    #     Q(date__lte=as_of) &
    #     Q(type='expense')
    # )

    filtered_transactions = Transaction.objects.filter(
        property__in=properties, date__lte=as_of, type='expense'
    )

    # Get a list of unique categories from the filtered transactions
    unique_categories = list(
        filtered_transactions.values_list('category', flat=True).distinct()
    ) or []
    # Initialize the expenses dictionary with unique categories
    expenses = {
        get_category_name(category): {'ytd': 0, 'all_time': 0}
        for category in unique_categories
    }
    # Add the 'total' key to the expenses dictionary
    expenses['total'] = {'ytd': 0, 'all_time': 0}

    # Adding rent category to collect in one for loop
    unique_categories.insert(0, 'rent')

    for category in unique_categories:

        cf_queryset = Transaction.objects.filter(
            property__in=properties, category=category
        )
        queryset_ytd = cf_queryset.filter(
            date__range=(current_year_start, as_of)
        )
        queryset_all_time = cf_queryset.filter(date__lte=as_of)
        if not default_currency_for_all_data:
            cf_ytd = queryset_ytd.aggregate(Sum('amount'))['amount__sum'] or 0
            cf_all_time = (
                queryset_all_time.aggregate(Sum('amount'))['amount__sum'] or 0
            )
        else:
            queryset_ytd = queryset_ytd.values(
                'date', 'currency', 'amount'
            ).all()
            cf_ytd = 0
            for transaction in queryset_ytd:
                fx_rate = FX.get_rate(
                    transaction['currency'],
                    target_currency,
                    transaction['date'],
                )['FX']
                cf_ytd += transaction['amount'] * fx_rate

            queryset_all_time = queryset_all_time.values(
                'date', 'currency', 'amount'
            ).all()
            cf_all_time = 0
            for transaction in queryset_all_time:
                fx_rate = FX.get_rate(
                    transaction['currency'],
                    target_currency,
                    transaction['date'],
                )['FX']
                cf_all_time += transaction['amount'] * fx_rate

        if category == 'rent':
            rent_ytd = cf_ytd
            rent_all_time = cf_all_time
        else:
            category_name = get_category_name(category)
            expenses[category_name]['ytd'] = round(float(cf_ytd), digits)
            expenses[category_name]['all_time'] = round(float(cf_all_time), digits)

            expenses['total']['ytd'] += cf_ytd
            expenses['total']['all_time'] += cf_all_time

    return expenses, rent_ytd, rent_all_time, unique_categories
