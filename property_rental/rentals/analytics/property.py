"""User-scoped raw property valuation history analytics."""

from dataclasses import dataclass
from datetime import date

from django.shortcuts import get_object_or_404

from rentals.analytics.contracts import SeriesDefinition
from rentals.models import Property


@dataclass(frozen=True)
class PropertyValuationResponse:
    metric: str
    grain: str
    currency: str | None
    scale: int
    start: date
    end: date
    status: str
    series: tuple[SeriesDefinition, ...]
    points: tuple[dict[str, object], ...]


def _point_status(total_value, debt):
    if total_value is None and debt is None:
        return "missing_value_and_debt"
    if total_value is None:
        return "missing_value"
    if debt is None:
        return "missing_debt"
    return "ok"


def _valuation_point(period, total_value, debt, status):
    return {
        "period_start": period,
        "period_end": period,
        "total_value": float(total_value) if total_value is not None else None,
        "debt": float(debt) if debt is not None else None,
        "equity": (
            float(total_value - debt)
            if total_value is not None and debt is not None
            else None
        ),
        "status": status,
    }


def _interpolate_value(before_value, after_value, before_date, after_date, target_date):
    if before_value is None or after_value is None:
        return None
    span = (after_date - before_date).days
    if span <= 0:
        return before_value
    elapsed = (target_date - before_date).days
    return before_value + (after_value - before_value) * elapsed / span


def property_valuation_history(user, property_id, end, start=None):
    """Return every owned valuation record through ``end`` without scaling."""
    property_ = get_object_or_404(
        Property.objects.filter(owned_by__user=user), pk=property_id
    )
    valuations = tuple(
        property_.capital.filter(capital_structure_date__lte=end).order_by(
            "capital_structure_date", "id"
        )
    )
    points = []
    if start is not None:
        before = next(
            (
                valuation
                for valuation in reversed(valuations)
                if valuation.capital_structure_date <= start
            ),
            None,
        )
        after = next(
            (
                valuation
                for valuation in valuations
                if valuation.capital_structure_date > start
            ),
            None,
        )
        if before is not None and before.capital_structure_date != start:
            if after is not None:
                total_value = _interpolate_value(
                    before.capital_structure_value,
                    after.capital_structure_value,
                    before.capital_structure_date,
                    after.capital_structure_date,
                    start,
                )
                debt = _interpolate_value(
                    before.capital_structure_debt,
                    after.capital_structure_debt,
                    before.capital_structure_date,
                    after.capital_structure_date,
                    start,
                )
                points.append(_valuation_point(start, total_value, debt, "interpolated"))
            else:
                points.append(
                    _valuation_point(
                        start,
                        before.capital_structure_value,
                        before.capital_structure_debt,
                        "carried_forward",
                    )
                )

    for valuation in valuations:
        if start is not None and valuation.capital_structure_date < start:
            continue
        total_value = valuation.capital_structure_value
        debt = valuation.capital_structure_debt
        points.append(
            _valuation_point(
                valuation.capital_structure_date,
                total_value,
                debt,
                _point_status(total_value, debt),
            )
        )

    if property_.currency is None:
        status = "missing_currency"
    elif not valuations:
        status = "missing_valuation"
    elif any(point["status"].startswith("missing_") for point in points):
        status = "partial_valuation"
    else:
        status = "ok"

    return PropertyValuationResponse(
        metric="property_valuation",
        grain="record",
        currency=property_.currency.upper() if property_.currency else None,
        scale=1,
        start=(
            start
            if start is not None
            else (valuations[0].capital_structure_date if valuations else end)
        ),
        end=end,
        status=status,
        series=(
            SeriesDefinition("total_value", "Total value", "total"),
            SeriesDefinition("debt", "Debt", "debt"),
            SeriesDefinition("equity", "Equity", "equity"),
        ),
        points=tuple(points),
    )
