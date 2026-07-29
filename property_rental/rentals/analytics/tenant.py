"""User-scoped expected-versus-received tenant rent analytics."""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.shortcuts import get_object_or_404
from networkx import NetworkXException

from rentals.analytics.cash_flow import _calendar_periods, _period_start
from rentals.analytics.contracts import SeriesDefinition
from rentals.models import Tenant, Transaction
from rentals.services.fx import preload_converter


ISSUE_ORDER = (
    "missing_rent_rate",
    "missing_expected_currency",
    "missing_expected_fx",
    "missing_received_currency",
    "missing_received_fx",
    "incomplete_opening_history",
    "incomplete_cumulative_history",
)


@dataclass(frozen=True)
class TenantRentPerformanceResponse:
    metric: str
    grain: str
    currency: str
    scale: int
    start: date
    end: date
    opening_arrears: float | None
    opening_issues: tuple[str, ...]
    status: str
    issues: tuple[str, ...]
    series: tuple[SeriesDefinition, ...]
    points: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class _ConvertibleAmount:
    amount: object
    currency: str
    date: date


def _next_month(month):
    if month.month == 12:
        return month.replace(year=month.year + 1, month=1)
    return month.replace(month=month.month + 1)


def _due_dates(tenant, start, end):
    month = tenant.lease_start.replace(day=1)
    final_month = end.replace(day=1)
    if tenant.lease_end is not None:
        final_month = min(final_month, tenant.lease_end.replace(day=1))
    while month <= final_month:
        payday = min(tenant.payday, calendar.monthrange(month.year, month.month)[1])
        due_date = month.replace(day=payday)
        if (
            start <= due_date <= end
            and tenant.lease_start <= due_date
            and (tenant.lease_end is None or due_date <= tenant.lease_end)
        ):
            yield due_date
        month = _next_month(month)


def _effective_rate(rent_history, due_date):
    rate = None
    for candidate in rent_history:
        if candidate.date_rent_set > due_date:
            break
        rate = candidate
    return rate


def _converted(converter, amount, currency, target_currency, as_of):
    if not currency:
        return None, "missing_currency"
    try:
        return (
            float(converter.convert(amount, currency, target_currency, as_of)),
            None,
        )
    except (ValueError, LookupError, NetworkXException):
        return None, "missing_fx"


def _append_issue(issues, issue):
    if issue not in issues:
        issues.append(issue)


def _ordered_issues(*groups):
    present = {issue for group in groups for issue in group}
    return tuple(issue for issue in ISSUE_ORDER if issue in present)


def _conversion_issue(role, error):
    return f"missing_{role}_{error.removeprefix('missing_')}"


def _status_from_issues(issues):
    if "missing_rent_rate" in issues:
        return "missing_rent_rate"
    if any(issue.endswith("_currency") for issue in issues):
        return "missing_currency"
    if any(issue.endswith("_fx") for issue in issues):
        return "missing_fx"
    if issues:
        return "incomplete_history"
    return "ok"


def _response_status(point_statuses):
    missing = [status for status in point_statuses if status != "ok"]
    if not missing:
        return "ok"
    if len(missing) == len(point_statuses) and len(set(missing)) == 1:
        return missing[0]
    return "partial_data"


def tenant_rent_performance(user, tenant_id, filters):
    """Return contractual rent performance in reporting currency.

    ``variance``, ``opening_arrears``, and ``cumulative_arrears`` all use
    received-minus-expected signs: negative means rent remains unpaid and
    positive means the tenant has overpaid. Contractual due dates are used
    directly; the collections scheduler's current-month grace is not applied.
    """
    tenant = get_object_or_404(
        Tenant.objects.select_related("property").filter(
            property__owned_by__user=user
        ),
        pk=tenant_id,
    )
    rent_history = tuple(
        tenant.rent_history.filter(date_rent_set__lte=filters.end).order_by(
            "date_rent_set", "id"
        )
    )
    transactions = tuple(
        Transaction.objects.filter(
            tenant=tenant,
            property=tenant.property,
            category="rent",
            date__range=(tenant.lease_start, filters.end),
        ).order_by("date", "id")
    )
    due_dates = tuple(_due_dates(tenant, tenant.lease_start, filters.end))
    rate_rows = tuple(
        _effective_rate(rent_history, due_date) for due_date in due_dates
    )
    convertible_rates = tuple(
        _ConvertibleAmount(rate.rent, rate.currency, due_date)
        for due_date, rate in zip(due_dates, rate_rows, strict=True)
        if rate is not None and rate.currency
    )
    converter = preload_converter(transactions + convertible_rates, filters.currency)

    opening_expected = 0.0
    opening_received = 0.0
    opening_issues = []
    expected_by_period = defaultdict(float)
    expected_issues_by_period = defaultdict(list)
    for due_date, rate in zip(due_dates, rate_rows, strict=True):
        is_opening = due_date < filters.start
        period = None if is_opening else _period_start(due_date, filters.grain)
        if rate is None:
            if is_opening:
                _append_issue(opening_issues, "missing_rent_rate")
            else:
                _append_issue(
                    expected_issues_by_period[period], "missing_rent_rate"
                )
            continue
        value, error = _converted(
            converter, rate.rent, rate.currency, filters.currency, due_date
        )
        if is_opening and error:
            _append_issue(opening_issues, _conversion_issue("expected", error))
        elif is_opening:
            opening_expected += value
        elif error:
            _append_issue(
                expected_issues_by_period[period],
                _conversion_issue("expected", error),
            )
        else:
            expected_by_period[period] += value

    received_by_period = defaultdict(float)
    received_issues_by_period = defaultdict(list)
    for transaction in transactions:
        is_opening = transaction.date < filters.start
        period = (
            None if is_opening else _period_start(transaction.date, filters.grain)
        )
        value, error = _converted(
            converter,
            transaction.amount,
            transaction.currency,
            filters.currency,
            transaction.date,
        )
        if is_opening and error:
            _append_issue(opening_issues, _conversion_issue("received", error))
        elif is_opening:
            opening_received += value
        elif error:
            _append_issue(
                received_issues_by_period[period],
                _conversion_issue("received", error),
            )
        else:
            received_by_period[period] += value

    opening_arrears = (
        opening_received - opening_expected if not opening_issues else None
    )
    points = []
    point_statuses = []
    cumulative = opening_arrears or 0.0
    cumulative_issue = (
        None if opening_arrears is not None else "incomplete_opening_history"
    )
    for period_start, period_end in _calendar_periods(filters):
        value_issues = _ordered_issues(
            expected_issues_by_period[period_start],
            received_issues_by_period[period_start],
        )
        expected = (
            None
            if expected_issues_by_period[period_start]
            else expected_by_period[period_start]
        )
        received = (
            None
            if received_issues_by_period[period_start]
            else received_by_period[period_start]
        )
        point_issues = _ordered_issues(
            value_issues, (cumulative_issue,) if cumulative_issue else ()
        )
        if not value_issues:
            variance = received - expected
            if cumulative_issue is None:
                cumulative += variance
            cumulative_arrears = cumulative if cumulative_issue is None else None
        else:
            variance = None
            cumulative_arrears = None
            if cumulative_issue is None:
                cumulative_issue = "incomplete_cumulative_history"
        status = _status_from_issues(point_issues)
        point_statuses.append(status)
        points.append(
            {
                "period_start": period_start,
                "period_end": period_end,
                "expected": expected,
                "received": received,
                "variance": variance,
                "cumulative_arrears": cumulative_arrears,
                "status": status,
                "issues": point_issues,
            }
        )

    ordered_opening_issues = _ordered_issues(
        opening_issues,
        ("incomplete_opening_history",) if opening_arrears is None else (),
    )
    response_issues = _ordered_issues(
        ordered_opening_issues, *(point["issues"] for point in points)
    )

    return TenantRentPerformanceResponse(
        metric="tenant_rent_performance",
        grain=filters.grain.value,
        currency=filters.currency,
        scale=1,
        start=filters.start,
        end=filters.end,
        opening_arrears=opening_arrears,
        opening_issues=ordered_opening_issues,
        status=_response_status(point_statuses),
        issues=response_issues,
        series=(
            SeriesDefinition("expected", "Expected rent", "expected"),
            SeriesDefinition("received", "Received rent", "received"),
            SeriesDefinition("variance", "Variance", "variance"),
            SeriesDefinition(
                "cumulative_arrears", "Cumulative arrears", "cumulative"
            ),
        ),
        points=tuple(points),
    )
