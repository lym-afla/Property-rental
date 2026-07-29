"""User-scoped portfolio summary, yield, exposure, and occupancy analytics."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db.models import Prefetch

from rentals.analytics.cash_flow import _calendar_periods, _period_start
from rentals.analytics.contracts import SeriesDefinition, TimeSeriesResponse
from rentals.constants import INCOME_CATEGORIES
from rentals.models import Property, Property_capital_structure, Tenant, Transaction
from rentals.services.fx import preload_converter


EXPOSURE_MEASURES = {
    "property_value": "Property value",
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
    debt: float
    equity: float | None
    valuation_status: str


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
    annualized_revenue: float | None
    annualized_costs: float | None
    gross_yield: float | None
    net_yield: float | None
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
class CurrencyExposureResponse:
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
    coverage: tuple["ExposureCoverage", ...]


@dataclass(frozen=True)
class ExposureCoverage:
    period_start: date
    period_end: date
    currency: str
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
    return (property_.currency or reporting_currency).upper()


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
    """Return annualized selected-period yields on the latest known valuation."""
    properties = _scoped_properties(user, filters)
    totals = _transaction_totals(properties, filters.currency)
    selected_days = (filters.end - filters.start).days + 1
    annualization = 365.0 / selected_days
    value_snapshots = []
    value_rows = []
    for property_ in properties:
        valuation = _latest_capital(property_, "capital_structure_value", filters.end)
        value_rows.append(valuation)
        if valuation is not None:
            value_snapshots.append(
                (
                    valuation.capital_structure_value,
                    _native_currency(property_, filters.currency),
                    filters.end,
                )
            )
    converted_values = iter(_convert_snapshots(value_snapshots, filters.currency))

    rows = []
    for property_, valuation in zip(properties, value_rows, strict=True):
        revenue, costs = totals[property_.id]
        annualized_revenue = revenue * annualization
        annualized_costs = costs * annualization
        if valuation is None:
            rows.append(
                YieldRow(
                    property_id=property_.id,
                    property_name=property_.name,
                    valuation_date=None,
                    property_value=None,
                    annualized_revenue=annualized_revenue,
                    annualized_costs=annualized_costs,
                    gross_yield=None,
                    net_yield=None,
                    status="missing_valuation",
                )
            )
            continue

        property_value = next(converted_values)
        status = (
            "zero_valuation"
            if property_value <= 0
            else (
                "stale_valuation"
                if valuation.capital_structure_date < filters.start
                else "ok"
            )
        )
        has_denominator = property_value > 0
        rows.append(
            YieldRow(
                property_id=property_.id,
                property_name=property_.name,
                valuation_date=valuation.capital_structure_date,
                property_value=property_value,
                annualized_revenue=annualized_revenue,
                annualized_costs=annualized_costs,
                gross_yield=(
                    annualized_revenue / property_value * 100.0
                    if has_denominator
                    else None
                ),
                net_yield=(
                    (annualized_revenue - annualized_costs)
                    / property_value
                    * 100.0
                    if has_denominator
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
            for tenant in property_.analytics_tenants
        )
        and (property_.sold is None or property_.sold >= capacity_date)
    }
    occupied_start = period_end if snapshot else period_start
    occupied_ids = {
        property_.id
        for property_ in properties
        if property_.id in capacity_ids
        and any(
            tenant.lease_start <= period_end
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


def _valuation_exposure(properties, filters, periods, measure):
    field = {
        "property_value": "capital_structure_value",
        "debt": "capital_structure_debt",
    }[measure]
    snapshots = []
    positions = []
    coverage = []
    active_positions = {}
    for period_index, (period_start, period_end) in enumerate(periods):
        as_of = min(period_end, filters.end)
        active = [
            property_
            for property_ in properties
            if property_.sold is None or property_.sold >= period_start
        ]
        for currency in {
            _native_currency(property_, filters.currency) for property_ in properties
        }:
            currency_properties = [
                property_
                for property_ in active
                if _native_currency(property_, filters.currency) == currency
            ]
            capital_rows = [
                _latest_capital(property_, field, as_of)
                for property_ in currency_properties
            ]
            present = [row for row in capital_rows if row is not None]
            if not currency_properties:
                status = "no_exposure"
            elif not present:
                status = "missing_valuation"
            elif len(present) != len(currency_properties):
                status = "partial_valuation"
            elif any(row.capital_structure_date < period_start for row in present):
                status = "stale_valuation"
            else:
                status = "ok"
            coverage.append(
                ExposureCoverage(period_start, period_end, currency, status)
            )
            active_positions[(period_index, currency)] = bool(currency_properties)
        for property_ in active:
            capital = _latest_capital(property_, field, as_of)
            if capital is None:
                continue
            snapshots.append(
                (
                    getattr(capital, field),
                    _native_currency(property_, filters.currency),
                    as_of,
                )
            )
            positions.append(
                (period_index, _native_currency(property_, filters.currency))
            )
    converted = _convert_snapshots(snapshots, filters.currency)
    values = defaultdict(float)
    for position, value in zip(positions, converted, strict=True):
        values[position] += value
    for position, has_properties in active_positions.items():
        if has_properties and not any(
            item[0] == position[0] and item[1] == position[1]
            for item in positions
        ):
            values[position] = None
    return values, tuple(coverage)


def _rental_income_exposure(properties, filters):
    native_currencies = {
        property_.id: _native_currency(property_, filters.currency)
        for property_ in properties
    }
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
                native_currencies[transaction.property_id],
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


def currency_exposure(user, filters, measure="property_value"):
    """Return the selected measure grouped by native property currency."""
    if measure not in EXPOSURE_MEASURES:
        raise ValueError(f"Unsupported currency exposure measure: {measure}")
    properties = _scoped_properties(user, filters)
    periods = _calendar_periods(filters)
    currencies = tuple(
        sorted({_native_currency(property_, filters.currency) for property_ in properties})
    )
    points = []
    if measure == "rental_income":
        values = _rental_income_exposure(properties, filters)
        coverage = ()
    else:
        values, coverage = _valuation_exposure(properties, filters, periods, measure)
    for period_index, (period_start, period_end) in enumerate(periods):
        point = {"period_start": period_start, "period_end": period_end}
        for currency in currencies:
            key = (
                (period_start, currency)
                if measure == "rental_income"
                else (period_index, currency)
            )
            point[currency] = values[key]
        points.append(point)
    return CurrencyExposureResponse(
        metric="currency_exposure",
        measure=measure,
        measure_label=EXPOSURE_MEASURES[measure],
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        series=tuple(
            SeriesDefinition(currency, currency, "native_currency")
            for currency in currencies
        ),
        points=tuple(points),
        coverage=coverage,
    )


def portfolio_summary(user, filters):
    """Return selected-period portfolio KPIs with explicit valuation status."""
    properties = _scoped_properties(user, filters)
    active_properties = tuple(
        property_
        for property_ in properties
        if property_.sold is None or property_.sold >= filters.end
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
    value_snapshots = [
        (
            row.capital_structure_value,
            _native_currency(property_, filters.currency),
            filters.end,
        )
        for property_, row in zip(active_properties, value_rows, strict=True)
        if row is not None
    ]
    debt_snapshots = [
        (
            row.capital_structure_debt,
            _native_currency(property_, filters.currency),
            filters.end,
        )
        for property_, row in zip(active_properties, debt_rows, strict=True)
        if row is not None
    ]
    property_value = (
        sum(_convert_snapshots(value_snapshots, filters.currency))
        if all(row is not None for row in value_rows)
        else None
    )
    debt = sum(_convert_snapshots(debt_snapshots, filters.currency))
    if any(row is None for row in value_rows):
        valuation_status = "missing_valuation"
    elif any(row.capital_structure_date < filters.start for row in value_rows):
        valuation_status = "stale_valuation"
    else:
        valuation_status = "ok"
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
        equity=property_value - debt if property_value is not None else None,
        valuation_status=valuation_status,
    )
