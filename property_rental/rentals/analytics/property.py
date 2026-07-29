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


def property_valuation_history(user, property_id, end):
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
    for valuation in valuations:
        total_value = valuation.capital_structure_value
        debt = valuation.capital_structure_debt
        points.append(
            {
                "period_start": valuation.capital_structure_date,
                "period_end": valuation.capital_structure_date,
                "total_value": (
                    float(total_value) if total_value is not None else None
                ),
                "debt": float(debt) if debt is not None else None,
                "equity": (
                    float(total_value - debt)
                    if total_value is not None and debt is not None
                    else None
                ),
                "status": _point_status(total_value, debt),
            }
        )

    if property_.currency is None:
        status = "missing_currency"
    elif not valuations:
        status = "missing_valuation"
    elif any(point["status"] != "ok" for point in points):
        status = "partial_valuation"
    else:
        status = "ok"

    return PropertyValuationResponse(
        metric="property_valuation",
        grain="record",
        currency=property_.currency.upper() if property_.currency else None,
        scale=1,
        start=(valuations[0].capital_structure_date if valuations else end),
        end=end,
        status=status,
        series=(
            SeriesDefinition("total_value", "Total value", "total"),
            SeriesDefinition("debt", "Debt", "debt"),
            SeriesDefinition("equity", "Equity", "equity"),
        ),
        points=tuple(points),
    )
