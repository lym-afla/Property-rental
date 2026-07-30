"""Shared, user-scoped annual and year-to-date profit and loss statements."""

from dataclasses import dataclass
from datetime import date

from rentals.constants import INCOME_CATEGORIES, TRANSACTION_CATEGORIES
from rentals.models import Transaction
from rentals.services.fx import preload_converter


@dataclass(frozen=True)
class ProfitLossColumn:
    key: str
    label: str
    start: date
    end: date


@dataclass(frozen=True)
class ProfitLossRow:
    key: str
    label: str
    kind: str
    values: dict[str, float]


@dataclass(frozen=True)
class ProfitLossResponse:
    metric: str
    currency: str
    scale: int
    end: date
    columns: tuple[ProfitLossColumn, ...]
    rows: tuple[ProfitLossRow, ...]

    @property
    def rows_by_key(self):
        return {row.key: row for row in self.rows}

    @property
    def total_revenue(self):
        return self.rows_by_key["total_revenue"].values

    @property
    def total_expenses(self):
        return self.rows_by_key["total_expenses"].values

    @property
    def net_income(self):
        return self.rows_by_key["net_income"].values


def _columns(first_year: int, end: date):
    annual = tuple(
        ProfitLossColumn(
            key=str(year),
            label=str(year),
            start=date(year, 1, 1),
            end=end if year == end.year else date(year, 12, 31),
        )
        for year in range(first_year, end.year + 1)
    )
    return annual + (
        ProfitLossColumn(
            key="ytd",
            label="YTD",
            start=end.replace(month=1, day=1),
            end=end,
        ),
    )


def profit_and_loss(user, end, currency, property_ids=()):
    """Return one canonical P&L statement for a portfolio or property scope."""
    queryset = Transaction.objects.filter(
        property__owned_by__user=user,
        date__lte=end,
    )
    if property_ids:
        queryset = queryset.filter(property_id__in=property_ids)
    transactions = tuple(queryset.order_by("date", "id"))
    first_year = transactions[0].date.year if transactions else end.year
    columns = _columns(first_year, end)
    values = {
        key: {column.key: 0.0 for column in columns}
        for key, _label in TRANSACTION_CATEGORIES
    }
    converter = preload_converter(transactions, currency)

    for transaction in transactions:
        converted = float(
            converter.convert(
                transaction.amount,
                transaction.currency,
                currency,
                transaction.date,
            )
        )
        signed = (
            converted
            if transaction.category in INCOME_CATEGORIES
            else -abs(converted)
        )
        values[transaction.category][str(transaction.date.year)] += signed
        if transaction.date.year == end.year:
            values[transaction.category]["ytd"] += signed

    rows = []
    for key, label in TRANSACTION_CATEGORIES:
        if any(values[key].values()):
            rows.append(
                ProfitLossRow(
                    key=key,
                    label=label,
                    kind="income" if key in INCOME_CATEGORIES else "expense",
                    values=values[key],
                )
            )

    total_revenue = {
        column.key: sum(
            values[key][column.key]
            for key, _label in TRANSACTION_CATEGORIES
            if key in INCOME_CATEGORIES
        )
        for column in columns
    }
    total_expenses = {
        column.key: sum(
            values[key][column.key]
            for key, _label in TRANSACTION_CATEGORIES
            if key not in INCOME_CATEGORIES
        )
        for column in columns
    }
    net_income = {
        column.key: total_revenue[column.key] + total_expenses[column.key]
        for column in columns
    }
    rows.extend(
        (
            ProfitLossRow(
                "total_revenue", "Total revenue", "total_revenue", total_revenue
            ),
            ProfitLossRow(
                "total_expenses", "Total expenses", "total_expenses", total_expenses
            ),
            ProfitLossRow("net_income", "Net income", "net_income", net_income),
        )
    )
    return ProfitLossResponse(
        metric="profit_and_loss",
        currency=currency,
        scale=1,
        end=end,
        columns=columns,
        rows=tuple(rows),
    )
