"""User-scoped portfolio summary, yield, breakdown, and occupancy analytics."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch

from rentals.analytics.cash_flow import _calendar_periods, _period_start
from rentals.analytics.contracts import SeriesDefinition, TimeSeriesResponse
from rentals.constants import INCOME_CATEGORIES
from rentals.models import Property, Property_capital_structure, Tenant, Transaction
from rentals.services.fx import preload_converter


PROPERTY_BREAKDOWN_MEASURES = {
    "property_value": "Property value",
    "equity": "Equity",
    "debt": "Debt",
    "rental_income": "Rental income",
}


@dataclass(frozen=True)
class PortfolioSummary:
    currency: str
    scale: int
    start: date
    end: date
    property_count: int
    rental_inventory_count: int
    occupied: int
    occupancy_rate: float
    revenue: float
    costs: float
    net_income: float
    property_value: float | None
    debt: float | None
    equity: float | None
    valuation_status: str
    property_value_status: str
    debt_status: str


@dataclass(frozen=True)
class ContributionRow:
    property_id: int
    property_name: str
    revenue: float
    costs: float
    net_income: float
    portfolio_share: float | None


@dataclass(frozen=True)
class ContributionResponse:
    metric: str
    currency: str
    scale: int
    start: date
    end: date
    portfolio_net_income: float
    rows: tuple[ContributionRow, ...]


@dataclass(frozen=True)
class YieldRow:
    property_id: int
    property_name: str
    valuation_date: date | None
    property_value: float | None
    debt: float | None
    equity: float | None
    annualized_revenue: float | None
    annualized_costs: float | None
    gross_yield: float | None
    equity_yield: float | None
    status: str


@dataclass(frozen=True)
class YieldResponse:
    metric: str
    currency: str
    scale: int
    start: date
    end: date
    rows: tuple[YieldRow, ...]


@dataclass(frozen=True)
class PropertyBreakdownResponse:
    metric: str
    measure: str
    measure_label: str
    grain: str
    currency: str
    scale: int
    start: date
    end: date
    series: tuple[SeriesDefinition, ...]
    points: tuple[dict[str, object], ...]
    coverage: tuple["PropertyBreakdownCoverage", ...]


@dataclass(frozen=True)
class PropertyBreakdownCoverage:
    period_start: date
    period_end: date
    property_id: int
    status: str


@dataclass(frozen=True)
class _ConvertibleAmount:
    amount: object
    currency: str
    date: date


def _scoped_properties(user, filters):
    properties = Property.objects.filter(owned_by__user=user)
    if filters.property_ids:
        properties = properties.filter(id__in=filters.property_ids)
    return tuple(
        properties.order_by("id").prefetch_related(
            Prefetch(
                "transactions",
                queryset=Transaction.objects.filter(
                    date__range=(filters.start, filters.end)
                ).order_by("date", "id"),
                to_attr="analytics_transactions",
            ),
            Prefetch(
                "capital",
                queryset=Property_capital_structure.objects.filter(
                    capital_structure_date__lte=filters.end
                ).order_by("capital_structure_date", "id"),
                to_attr="analytics_capital",
            ),
            Prefetch(
                "tenants",
                queryset=Tenant.objects.filter(
                    lease_start__lte=filters.end
                ).order_by("lease_start", "id"),
                to_attr="analytics_tenants",
            ),
        )
    )


def _native_currency(property_, reporting_currency):
    return property_.currency.upper() if property_.currency else None


def _transaction_totals(properties, reporting_currency):
    transactions = tuple(
        transaction
        for property_ in properties
        for transaction in property_.analytics_transactions
    )
    converter = preload_converter(transactions, reporting_currency)
    totals = defaultdict(lambda: [0.0, 0.0])
    for transaction in transactions:
        converted = float(
            converter.convert(
                transaction.amount,
                transaction.currency,
                reporting_currency,
                transaction.date,
            )
        )
        if transaction.category in INCOME_CATEGORIES:
            totals[transaction.property_id][0] += converted
        else:
            totals[transaction.property_id][1] += abs(converted)
    return totals


def _latest_capital(property_, field, as_of):
    candidates = [
        row
        for row in property_.analytics_capital
        if row.capital_structure_date <= as_of and getattr(row, field) is not None
    ]
    return candidates[-1] if candidates else None


def _convert_snapshots(snapshots, reporting_currency):
    convertible = tuple(
        _ConvertibleAmount(amount, native_currency, as_of)
        for amount, native_currency, as_of in snapshots
    )
    converter = preload_converter(convertible, reporting_currency)
    return tuple(
        float(converter.convert(row.amount, row.currency, reporting_currency, row.date))
        for row in convertible
    )


def property_contribution(user, filters):
    """Return signed selected-period net-income contribution by property."""
    properties = _scoped_properties(user, filters)
    totals = _transaction_totals(properties, filters.currency)
    portfolio_net_income = sum(revenue - costs for revenue, costs in totals.values())
    rows = []
    for property_ in properties:
        revenue, costs = totals[property_.id]
        net_income = revenue - costs
        share = (
            net_income / portfolio_net_income * 100.0
            if portfolio_net_income != 0
            else None
        )
        rows.append(
            ContributionRow(
                property_id=property_.id,
                property_name=property_.name,
                revenue=revenue,
                costs=costs,
                net_income=net_income,
                portfolio_share=share,
            )
        )
    return ContributionResponse(
        metric="property_contribution",
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        portfolio_net_income=portfolio_net_income,
        rows=tuple(rows),
    )


def property_yields(user, filters):
    """Return annualized selected-period yields on value and equity."""
    properties = tuple(
        property_
        for property_ in _scoped_properties(user, filters)
        if property_.sold is None or property_.sold > filters.end
    )
    totals = _transaction_totals(properties, filters.currency)
    selected_days = (filters.end - filters.start).days + 1
    annualization = 365.0 / selected_days
    capital_rows = []
    value_snapshots = []
    value_property_ids = []
    debt_snapshots = []
    debt_property_ids = []
    for property_ in properties:
        valuation = _latest_capital(property_, "capital_structure_value", filters.end)
        debt_row = _latest_capital(property_, "capital_structure_debt", filters.end)
        capital_rows.append((valuation, debt_row))
        native_currency = _native_currency(property_, filters.currency)
        if valuation is not None and native_currency is not None:
            value_snapshots.append(
                (
                    valuation.capital_structure_value,
                    native_currency,
                    valuation.capital_structure_date,
                )
            )
            value_property_ids.append(property_.id)
        if debt_row is not None and native_currency is not None:
            debt_snapshots.append(
                (
                    debt_row.capital_structure_debt,
                    native_currency,
                    debt_row.capital_structure_date,
                )
            )
            debt_property_ids.append(property_.id)
    converted_values = dict(
        zip(
            value_property_ids,
            _convert_snapshots(value_snapshots, filters.currency),
            strict=True,
        )
    )
    converted_debts = dict(
        zip(
            debt_property_ids,
            _convert_snapshots(debt_snapshots, filters.currency),
            strict=True,
        )
    )

    rows = []
    for property_, (valuation, debt_row) in zip(
        properties, capital_rows, strict=True
    ):
        revenue, costs = totals[property_.id]
        annualized_revenue = revenue * annualization
        annualized_costs = costs * annualization
        if _native_currency(property_, filters.currency) is None:
            rows.append(
                YieldRow(
                    property_id=property_.id,
                    property_name=property_.name,
                    valuation_date=(
                        valuation.capital_structure_date
                        if valuation is not None
                        else None
                    ),
                    property_value=None,
                    debt=None,
                    equity=None,
                    annualized_revenue=annualized_revenue,
                    annualized_costs=annualized_costs,
                    gross_yield=None,
                    equity_yield=None,
                    status="missing_currency",
                )
            )
            continue

        property_value = converted_values.get(property_.id)
        debt = converted_debts.get(property_.id)
        equity = (
            property_value - debt
            if property_value is not None and debt is not None
            else None
        )
        if property_value is not None and property_value < 0:
            status = "negative_valuation"
        elif property_value == 0:
            status = "zero_valuation"
        elif valuation is None or debt_row is None:
            status = "missing_valuation"
        elif equity < 0:
            status = "negative_equity"
        elif equity == 0:
            status = "zero_equity"
        elif (
            valuation.capital_structure_date < filters.start
            or debt_row.capital_structure_date < filters.start
        ):
            status = "stale_valuation"
        else:
            status = "ok"
        has_value_denominator = property_value is not None and property_value > 0
        has_equity_denominator = equity is not None and equity > 0
        rows.append(
            YieldRow(
                property_id=property_.id,
                property_name=property_.name,
                valuation_date=(
                    valuation.capital_structure_date
                    if valuation is not None
                    else None
                ),
                property_value=property_value,
                debt=debt,
                equity=equity,
                annualized_revenue=annualized_revenue,
                annualized_costs=annualized_costs,
                gross_yield=(
                    annualized_revenue / property_value * 100.0
                    if has_value_denominator
                    else None
                ),
                equity_yield=(
                    (annualized_revenue - annualized_costs) / equity * 100.0
                    if has_equity_denominator
                    else None
                ),
                status=status,
            )
        )
    return YieldResponse(
        metric="property_yields",
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        rows=tuple(rows),
    )


def _occupancy_counts(properties, period_start, period_end, snapshot=False):
    capacity_date = period_end if snapshot else period_start
    capacity_ids = {
        property_.id
        for property_ in properties
        if any(
            tenant.lease_start <= period_end
            and (property_.sold is None or tenant.lease_start < property_.sold)
            for tenant in property_.analytics_tenants
        )
        and (property_.sold is None or property_.sold > capacity_date)
    }
    occupied_start = period_end if snapshot else period_start
    occupied_ids = {
        property_.id
        for property_ in properties
        if property_.id in capacity_ids
        and any(
            tenant.lease_start <= period_end
            and (property_.sold is None or tenant.lease_start < property_.sold)
            and (tenant.lease_end is None or tenant.lease_end >= occupied_start)
            for tenant in property_.analytics_tenants
        )
    }
    return len(capacity_ids), len(occupied_ids)


def portfolio_occupancy(user, filters):
    """Return distinct-property occupied capacity for each calendar bucket."""
    properties = _scoped_properties(user, filters)
    points = []
    for period_start, period_end in _calendar_periods(filters):
        calculation_start = max(period_start, filters.start)
        calculation_end = min(period_end, filters.end)
        capacity, occupied = _occupancy_counts(
            properties, calculation_start, calculation_end
        )
        vacant = capacity - occupied
        points.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "capacity": capacity,
                "occupied": occupied,
                "vacant": vacant,
                "occupancy_rate": occupied / capacity * 100.0 if capacity else 0.0,
            }
        )
    return TimeSeriesResponse(
        metric="portfolio_occupancy",
        grain=filters.grain.value,
        currency=None,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=(
            SeriesDefinition("capacity", "Capacity", "capacity"),
            SeriesDefinition("occupied", "Occupied", "occupied"),
            SeriesDefinition("vacant", "Vacant", "vacant"),
            SeriesDefinition("occupancy_rate", "Occupancy rate", "percentage"),
        ),
        points=tuple(points),
    )


def _rental_income_by_property(properties, filters):
    transactions = tuple(
        transaction
        for property_ in properties
        for transaction in property_.analytics_transactions
        if transaction.category in INCOME_CATEGORIES
    )
    converter = preload_converter(transactions, filters.currency)
    values = defaultdict(float)
    for transaction in transactions:
        values[
            (
                _period_start(transaction.date, filters.grain),
                transaction.property_id,
            )
        ] += float(
            converter.convert(
                transaction.amount,
                transaction.currency,
                filters.currency,
                transaction.date,
            )
        )
    return values


def _property_breakdown_capital_values(properties, periods, filters, measure):
    fields = {
        "property_value": ("capital_structure_value",),
        "debt": ("capital_structure_debt",),
        "equity": ("capital_structure_value", "capital_structure_debt"),
    }[measure]
    snapshots = []
    positions = []
    values = {}
    statuses = {}
    for period_index, (period_start, period_end) in enumerate(periods):
        as_of = min(period_end, filters.end)
        for property_ in properties:
            if property_.sold is not None and property_.sold <= as_of:
                continue
            position = (period_index, property_.id)
            native_currency = _native_currency(property_, filters.currency)
            if native_currency is None:
                values[position] = None
                statuses[position] = "missing_currency"
                continue
            rows = tuple(_latest_capital(property_, field, as_of) for field in fields)
            if any(row is None for row in rows):
                values[position] = None
                statuses[position] = "missing_valuation"
                continue
            statuses[position] = (
                "stale_valuation"
                if any(row.capital_structure_date < period_start for row in rows)
                else "ok"
            )
            for field, row in zip(fields, rows, strict=True):
                snapshots.append(
                    (
                        getattr(row, field),
                        native_currency,
                        row.capital_structure_date,
                    )
                )
                positions.append(position)

    converted_components = defaultdict(list)
    converted = (
        _convert_snapshots(tuple(snapshots), filters.currency) if snapshots else ()
    )
    for position, value in zip(positions, converted, strict=True):
        converted_components[position].append(value)
    for position, components in converted_components.items():
        values[position] = (
            components[0]
            if measure != "equity"
            else components[0] - components[1]
        )
    return values, statuses


def property_breakdown(user, filters, measure="property_value"):
    """Return the selected measure grouped by stable property identifiers."""
    if measure not in PROPERTY_BREAKDOWN_MEASURES:
        raise ValueError(f"Unsupported property breakdown measure: {measure}")
    properties = _scoped_properties(user, filters)
    periods = _calendar_periods(filters)
    visible_properties = tuple(
        property_
        for property_ in properties
        if any(
            property_.sold is None
            or property_.sold > min(period_end, filters.end)
            for _, period_end in periods
        )
    )
    points = []
    coverage = []
    if measure == "rental_income":
        income = _rental_income_by_property(visible_properties, filters)
    else:
        capital_values, capital_statuses = _property_breakdown_capital_values(
            visible_properties, periods, filters, measure
        )
    for period_index, (period_start, period_end) in enumerate(periods):
        as_of = min(period_end, filters.end)
        point = {"period_start": period_start, "period_end": period_end}
        for property_ in visible_properties:
            if property_.sold is not None and property_.sold <= as_of:
                continue
            key = f"property_{property_.id}"
            if measure == "rental_income":
                point[key] = income[(period_start, property_.id)]
                continue
            position = (period_index, property_.id)
            point[key] = capital_values[position]
            coverage.append(
                PropertyBreakdownCoverage(
                    period_start=period_start,
                    period_end=period_end,
                    property_id=property_.id,
                    status=capital_statuses[position],
                )
            )
        points.append(point)
    return PropertyBreakdownResponse(
        metric="property_breakdown",
        measure=measure,
        measure_label=PROPERTY_BREAKDOWN_MEASURES[measure],
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=tuple(
            SeriesDefinition(
                f"property_{property_.id}",
                property_.name,
                "property",
            )
            for property_ in visible_properties
        ),
        points=tuple(points),
        coverage=tuple(coverage),
    )


def portfolio_summary(user, filters):
    """Return selected-period portfolio KPIs with explicit valuation status."""
    properties = _scoped_properties(user, filters)
    active_properties = tuple(
        property_
        for property_ in properties
        if property_.sold is None or property_.sold > filters.end
    )
    totals = _transaction_totals(properties, filters.currency)
    revenue = sum(values[0] for values in totals.values())
    costs = sum(values[1] for values in totals.values())
    inventory_count, occupied = _occupancy_counts(
        properties, filters.end, filters.end, snapshot=True
    )

    value_rows = [
        _latest_capital(property_, "capital_structure_value", filters.end)
        for property_ in active_properties
    ]
    debt_rows = [
        _latest_capital(property_, "capital_structure_debt", filters.end)
        for property_ in active_properties
    ]
    property_value_status = _summary_snapshot_status(
        active_properties, value_rows, filters.start, filters.currency
    )
    debt_status = _summary_snapshot_status(
        active_properties, debt_rows, filters.start, filters.currency
    )
    value_snapshots = [
        (
            row.capital_structure_value,
            _native_currency(property_, filters.currency),
            row.capital_structure_date,
        )
        for property_, row in zip(active_properties, value_rows, strict=True)
        if row is not None
        and _native_currency(property_, filters.currency) is not None
    ]
    debt_snapshots = [
        (
            row.capital_structure_debt,
            _native_currency(property_, filters.currency),
            row.capital_structure_date,
        )
        for property_, row in zip(active_properties, debt_rows, strict=True)
        if row is not None
        and _native_currency(property_, filters.currency) is not None
    ]
    property_value = (
        sum(_convert_snapshots(value_snapshots, filters.currency))
        if property_value_status in {"ok", "stale_valuation"}
        else None
    )
    debt = (
        sum(_convert_snapshots(debt_snapshots, filters.currency))
        if debt_status in {"ok", "stale_valuation"}
        else None
    )
    valuation_status = _combined_summary_status(
        property_value_status, debt_status
    )
    return PortfolioSummary(
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        property_count=len(active_properties),
        rental_inventory_count=inventory_count,
        occupied=occupied,
        occupancy_rate=occupied / inventory_count * 100.0 if inventory_count else 0.0,
        revenue=revenue,
        costs=costs,
        net_income=revenue - costs,
        property_value=property_value,
        debt=debt,
        equity=(
            property_value - debt
            if property_value is not None and debt is not None
            else None
        ),
        valuation_status=valuation_status,
        property_value_status=property_value_status,
        debt_status=debt_status,
    )


def _summary_snapshot_status(properties, rows, start, reporting_currency):
    if any(
        _native_currency(property_, reporting_currency) is None
        for property_ in properties
    ):
        return "missing_currency"
    if any(row is None for row in rows):
        return "missing_valuation"
    if any(row.capital_structure_date < start for row in rows):
        return "stale_valuation"
    return "ok"


def _combined_summary_status(property_value_status, debt_status):
    for status in ("missing_currency", "missing_valuation", "stale_valuation"):
        if status in {property_value_status, debt_status}:
            return status
    return "ok"
