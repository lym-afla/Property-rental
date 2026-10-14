"""User-scoped, calendar-bucketed portfolio cash-flow analytics."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Exists

from rentals.analytics.contracts import SeriesDefinition, TimeSeriesResponse
from rentals.constants import INCOME_CATEGORIES, TRANSACTION_CATEGORIES
from rentals.financial_semantics import deposit_signed_amount
from rentals.models import Transaction
from rentals.services.deposits import movements_for_user
from rentals.services.financials import convert_transactions
from rentals.services.fx import preload_converter


_CATEGORY_LABELS = dict(TRANSACTION_CATEGORIES)


@dataclass(frozen=True)
class _ConvertibleAmount:
    amount: object
    currency: str
    date: date


def _scoped_deposit_movements(user, filters):
    return movements_for_user(
        user,
        start=filters.start,
        end=filters.end,
        property_ids=filters.property_ids,
    )


def _signed_deposit_amounts(user, filters, transactions):
    """Signed deposit movements in scope, shaped for the FX converter.

    The transaction query carries a ``has_deposits`` flag so the common case
    (rows exist, no movements in scope) costs no extra query.
    """
    if transactions and not any(t.has_deposits for t in transactions):
        return []
    return [
        _ConvertibleAmount(
            deposit_signed_amount(movement.kind, movement.amount),
            movement.currency,
            movement.date,
        )
        for movement in _scoped_deposit_movements(user, filters).order_by(
            "date", "id"
        )
    ]


def _period_start(value: date, grain: str) -> date:
    if grain == "month":
        return value.replace(day=1)
    if grain == "quarter":
        return value.replace(month=((value.month - 1) // 3) * 3 + 1, day=1)
    return value.replace(month=1, day=1)


def _next_period_start(value: date, grain: str) -> date | None:
    if grain == "month":
        if value.month < 12:
            return value.replace(month=value.month + 1, day=1)
        if value.year == date.max.year:
            return None
        return value.replace(year=value.year + 1, month=1, day=1)
    if grain == "quarter":
        if value.month == 10:
            if value.year == date.max.year:
                return None
            return value.replace(year=value.year + 1, month=1, day=1)
        return value.replace(month=value.month + 3, day=1)
    if value.year == date.max.year:
        return None
    return value.replace(year=value.year + 1, month=1, day=1)


def _calendar_periods(filters):
    period_start = _period_start(filters.start, filters.grain)
    periods = []
    while period_start <= filters.end:
        next_start = _next_period_start(period_start, filters.grain)
        if next_start is None:
            periods.append((period_start, date.max))
            break
        periods.append((period_start, next_start - timedelta(days=1)))
        period_start = next_start
    return tuple(periods)


def _scoped_transactions(user, filters, flag_deposits=False):
    queryset = Transaction.objects.filter(
        property__owned_by__user=user,
        date__range=(filters.start, filters.end),
    )
    if flag_deposits:
        queryset = queryset.annotate(
            has_deposits=Exists(_scoped_deposit_movements(user, filters))
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
            kind=(
                "income_category"
                if key in INCOME_CATEGORIES
                else "expense_category"
            ),
        )
        for key in category_keys
    )


def portfolio_cash_flow(user, filters):
    """Return signed raw portfolio cash flow for each calendar period.

    A single transaction queryset is scoped through ``property.owned_by``
    before it is materialized; all subsequent category and calendar work is
    in memory.  FX conversion stays in the established financial service.
    """
    transactions = _scoped_transactions(user, filters, flag_deposits=True)
    deposit_amounts = _signed_deposit_amounts(user, filters, transactions)
    converter = preload_converter(
        transactions + deposit_amounts, filters.currency
    )
    category_keys = _category_keys(transactions, include_income=False)
    bucketed_transactions = _bucket_transactions(transactions, filters)
    bucketed_deposits = defaultdict(list)
    for amount in deposit_amounts:
        bucketed_deposits[_period_start(amount.date, filters.grain)].append(
            amount
        )
    periods = _calendar_periods(filters)
    points = []
    cumulative_net_income = 0.0

    for period_start, period_end in periods:
        category_rows = bucketed_transactions[period_start]
        point = {
            "period_start": max(period_start, filters.start),
            "period_end": min(period_end, filters.end),
        }
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
        if deposit_amounts:
            deposits = float(
                convert_transactions(
                    bucketed_deposits[period_start],
                    filters.currency,
                    period_end,
                    converter=converter,
                )
            )
            point.update(deposits=deposits, net_cash_flow=net_income + deposits)
        points.append(point)

    deposit_series = (
        (
            SeriesDefinition(
                "deposits", "Security deposits", "deposit_movement"
            ),
            SeriesDefinition("net_cash_flow", "Net cash flow", "net_cash"),
        )
        if deposit_amounts
        else ()
    )
    return TimeSeriesResponse(
        metric="portfolio_cash_flow",
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=_category_series(category_keys)
        + (
            SeriesDefinition("total_income", "Total income", "income_total"),
            SeriesDefinition("total_expenses", "Total expenses", "expense_total"),
            SeriesDefinition("net_income", "Net income", "net"),
            SeriesDefinition(
                "cumulative_net_income", "Cumulative net income", "cumulative"
            ),
        )
        + deposit_series,
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
        point = {
            "period_start": max(period_start, filters.start),
            "period_end": min(period_end, filters.end),
        }
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
