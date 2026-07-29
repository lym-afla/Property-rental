from datetime import date

import pytest
from django.test import RequestFactory
from rest_framework import serializers

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.api.analytics_serializers import TimeSeriesResponseSerializer


def test_filters_reject_end_before_start(landlord_user):
    """Changing the boundary check would permit an invalid analytics range."""
    request = RequestFactory().get(
        "/api/v1/analytics/portfolio/cash-flow/",
        {"start": "2026-07-31", "end": "2026-01-01", "grain": "month"},
    )

    with pytest.raises(serializers.ValidationError, match="end must be on or after start"):
        AnalyticsFilters.from_query_params(
            request.GET,
            default_currency=landlord_user.default_currency,
            effective_date=date(2026, 7, 31),
        )


def test_filters_parse_supported_query_parameters(landlord_user):
    """Changing query parsing would lose selected properties or typed values."""
    request = RequestFactory().get(
        "/api/v1/analytics/portfolio/cash-flow/",
        [
            ("start", "2026-01-01"),
            ("end", "2026-03-31"),
            ("grain", "quarter"),
            ("currency", "eur"),
            ("comparison", "previous_period"),
            ("property", "4"),
            ("property", "9"),
        ],
    )

    filters = AnalyticsFilters.from_query_params(
        request.GET,
        default_currency=landlord_user.default_currency,
        effective_date=date(2026, 7, 31),
    )

    assert filters.start == date(2026, 1, 1)
    assert filters.end == date(2026, 3, 31)
    assert filters.grain is Grain.QUARTER
    assert filters.currency == "EUR"
    assert filters.comparison == "previous_period"
    assert filters.property_ids == (4, 9)


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ({"grain": "week"}, "grain"),
        ({"currency": "US"}, "currency"),
        ({"property": "not-an-id"}, "property"),
    ],
)
def test_filters_reject_invalid_query_values(landlord_user, query, message):
    """Changing field validation would accept malformed analytics filters."""
    request = RequestFactory().get("/api/v1/analytics/", query)

    with pytest.raises(serializers.ValidationError) as exc_info:
        AnalyticsFilters.from_query_params(
            request.GET,
            default_currency=landlord_user.default_currency,
            effective_date=date(2026, 7, 31),
        )

    assert message in exc_info.value.detail


def test_time_series_serializer_requires_raw_scale():
    """Changing scale validation would allow display-scaled monetary values into the API."""
    serializer = TimeSeriesResponseSerializer(
        data={
            "metric": "portfolio_cash_flow",
            "grain": "month",
            "currency": "USD",
            "scale": 1000,
            "start": "2026-01-01",
            "end": "2026-01-31",
            "series": [],
            "points": [],
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["scale"]


def test_time_series_serializer_rejects_end_before_start():
    """Changing response validation would emit inverted ISO date boundaries."""
    serializer = TimeSeriesResponseSerializer(
        data={
            "metric": "portfolio_cash_flow",
            "grain": "month",
            "currency": "USD",
            "scale": 1,
            "start": "2026-02-01",
            "end": "2026-01-31",
            "series": [],
            "points": [],
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["end"]
