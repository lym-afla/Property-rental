"""User-scoped, calendar-bucketed portfolio cash-flow analytics."""

from collections import defaultdict
from datetime import date, timedelta

from rentals.analytics.contracts import SeriesDefinition, TimeSeriesResponse
from rentals.constants import INCOME_CATEGORIES, TRANSACTION_CATEGORIES
from rentals.models import Transaction
from rentals.services.financials import convert_transactions
from rentals.services.fx import preload_converter


_CATEGORY_LABELS = dict(TRANSACTION_CATEGORIES)


def _period_start(value: date, grain: str) -> date:
    if grain == "month":
        return value.replace(day=1)
    if grain == "quarter":
        return value.replace(month=((value.month - 1) // 3) * 3 + 1, day=1)
    return value.replace(month=1, day=1)


def _next_period_start(value: date, grain: str) -> date:
    if grain == "month":
        return (value.replace(day=28) + timedelta(days=4)).replace(day=1)
    if grain == "quarter":
        if value.month == 10:
            return value.replace(year=value.year + 1, month=1, day=1)
        return value.replace(month=value.month + 3, day=1)
    return value.replace(year=value.year + 1, month=1, day=1)


def _calendar_periods(filters):
    period_start = _period_start(filters.start, filters.grain)
    periods = []
    while period_start <= filters.end:
        next_start = _next_period_start(period_start, filters.grain)
        periods.append((period_start, next_start - timedelta(days=1)))
        period_start = next_start
    return tuple(periods)


def _scoped_transactions(user, filters):
    queryset = Transaction.objects.filter(
        property__owned_by__user=user,
        date__range=(filters.start, filters.end),
    )
    if filters.property_ids:
        queryset = queryset.filter(property_id__in=filters.property_ids)
    return list(queryset.order_by("date", "id"))


def _bucket_transactions(transactions, filters):
    buckets = defaultdict(lambda: defaultdict(list))
    for transaction in transactions:
        buckets[_period_start(transaction.date, filters.grain)][
            transaction.category
        ].append(transaction)
    return buckets


def _category_keys(transactions, include_income: bool):
    present_categories = {transaction.category for transaction in transactions}
    return tuple(
        key
        for key, _label in TRANSACTION_CATEGORIES
        if key in present_categories
        and ((key in INCOME_CATEGORIES) if include_income else True)
    )


def _expense_category_keys(transactions):
    present_categories = {transaction.category for transaction in transactions}
    return tuple(
        key
        for key, _label in TRANSACTION_CATEGORIES
        if key in present_categories and key not in INCOME_CATEGORIES
    )


def _category_total(rows, category, currency, as_of, converter):
    if not rows:
        return 0.0
    total = float(
        convert_transactions(rows, currency, as_of, converter=converter)
    )
    return total if category in INCOME_CATEGORIES else -abs(total)


def _category_series(category_keys):
    return tuple(
        SeriesDefinition(
            key=key,
            label=_CATEGORY_LABELS[key],
            kind="income" if key in INCOME_CATEGORIES else "expense",
        )
        for key in category_keys
    )


def portfolio_cash_flow(user, filters):
    """Return signed raw portfolio cash flow for each calendar period.

    A single transaction queryset is scoped through ``property.owned_by``
    before it is materialized; all subsequent category and calendar work is
    in memory.  FX conversion stays in the established financial service.
    """
    transactions = _scoped_transactions(user, filters)
    converter = preload_converter(transactions, filters.currency)
    category_keys = _category_keys(transactions, include_income=False)
    bucketed_transactions = _bucket_transactions(transactions, filters)
    periods = _calendar_periods(filters)
    points = []
    cumulative_net_income = 0.0

    for period_start, period_end in periods:
        category_rows = bucketed_transactions[period_start]
        point = {"period_start": period_start, "period_end": period_end}
        for category in category_keys:
            point[category] = _category_total(
                category_rows[category],
                category,
                filters.currency,
                period_end,
                converter,
            )
        total_income = sum(
            point[category] for category in category_keys if category in INCOME_CATEGORIES
        )
        total_expenses = sum(
            point[category] for category in category_keys if category not in INCOME_CATEGORIES
        )
        net_income = total_income + total_expenses
        cumulative_net_income += net_income
        point.update(
            total_income=total_income,
            total_expenses=total_expenses,
            net_income=net_income,
            cumulative_net_income=cumulative_net_income,
        )
        points.append(point)

    return TimeSeriesResponse(
        metric="portfolio_cash_flow",
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=_category_series(category_keys)
        + (
            SeriesDefinition("total_income", "Total income", "income"),
            SeriesDefinition("total_expenses", "Total expenses", "expense"),
            SeriesDefinition("net_income", "Net income", "net"),
            SeriesDefinition(
                "cumulative_net_income", "Cumulative net income", "cumulative"
            ),
        ),
        points=tuple(points),
    )


def expense_drivers(user, filters):
    """Return signed, backend-classified expense categories by calendar period."""
    transactions = _scoped_transactions(user, filters)
    converter = preload_converter(transactions, filters.currency)
    category_keys = _expense_category_keys(transactions)
    bucketed_transactions = _bucket_transactions(transactions, filters)
    points = []

    for period_start, period_end in _calendar_periods(filters):
        category_rows = bucketed_transactions[period_start]
        point = {"period_start": period_start, "period_end": period_end}
        for category in category_keys:
            point[category] = _category_total(
                category_rows[category],
                category,
                filters.currency,
                period_end,
                converter,
            )
        points.append(point)

    return TimeSeriesResponse(
        metric="expense_drivers",
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=_category_series(category_keys),
        points=tuple(points),
    )
