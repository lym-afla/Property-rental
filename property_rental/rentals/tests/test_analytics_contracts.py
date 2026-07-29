from datetime import date

import pytest
from django.test import RequestFactory
from rest_framework import serializers

from rentals.analytics.filters import AnalyticsFilters, Grain
from rentals.analytics.contracts import (
    CategoryValue,
    SeriesDefinition,
    TimeSeriesPoint,
    TimeSeriesResponse,
)
from rentals.api.analytics_serializers import (
    CategoryValueSerializer,
    TimeSeriesPointSerializer,
    TimeSeriesResponseSerializer,
)


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


def test_time_series_serializer_accepts_flattened_dynamic_series_points():
    """Nesting values would prevent endpoints from emitting the planned point contract."""
    serializer = TimeSeriesResponseSerializer(
        data={
            "metric": "portfolio_cash_flow",
            "grain": "month",
            "currency": "USD",
            "scale": 1,
            "start": "2026-01-01",
            "end": "2026-01-31",
            "series": [
                {"key": "income", "label": "Income", "kind": "positive"},
                {"key": "expenses", "label": "Expenses", "kind": "negative"},
            ],
            "points": [
                {
                    "period_start": "2026-01-01",
                    "period_end": "2026-01-31",
                    "income": "1250.00",
                    "expenses": "-425.50",
                }
            ],
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["points"][0] == {
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "income": "1250.00",
        "expenses": "-425.50",
    }


def test_time_series_point_serializer_flattens_typed_contract_values():
    """Leaving typed values nested would diverge service objects from API points."""
    point = TimeSeriesPoint(
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        values={"income": "1250.00", "expenses": "-425.50"},
    )

    assert TimeSeriesPointSerializer(point).data == {
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "income": "1250.00",
        "expenses": "-425.50",
    }


def test_time_series_response_serializer_emits_declared_flat_point_dictionaries():
    """Assuming only point dataclasses would break the declared response contract."""
    response = TimeSeriesResponse(
        metric="portfolio_cash_flow",
        grain="month",
        currency="USD",
        scale=1,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        series=(SeriesDefinition("income", "Income", "positive"),),
        points=(
            {
                "period_start": date(2026, 1, 1),
                "period_end": date(2026, 1, 31),
                "income": "1250.00",
            },
        ),
    )

    assert TimeSeriesResponseSerializer(response).data["points"] == [
        {
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "income": "1250.00",
        }
    ]


def test_time_series_response_serializer_omits_undeclared_point_keys():
    """Copying every point key would leak fields outside the declared series contract."""
    response = TimeSeriesResponse(
        metric="portfolio_cash_flow",
        grain="month",
        currency="USD",
        scale=1,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        series=(SeriesDefinition("income", "Income", "positive"),),
        points=(
            {
                "period_start": date(2026, 1, 1),
                "period_end": date(2026, 1, 31),
                "income": "1250.00",
                "internal_note": "must not be emitted",
            },
        ),
    )

    assert TimeSeriesResponseSerializer(response).data["points"] == [
        {
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "income": "1250.00",
        }
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [("start", "2026-1-01"), ("end", "2026-01-1")],
)
def test_filters_require_zero_padded_iso_dates(landlord_user, field, value):
    """Relaxing URL date syntax would violate stable YYYY-MM-DD URL state."""
    request = RequestFactory().get("/api/v1/analytics/", {field: value})

    with pytest.raises(serializers.ValidationError) as exc_info:
        AnalyticsFilters.from_query_params(
            request.GET,
            default_currency=landlord_user.default_currency,
            effective_date=date(2026, 7, 31),
        )

    assert field in exc_info.value.detail


def test_time_series_serializer_requires_zero_padded_iso_dates():
    """Relaxing response date syntax would emit boundaries outside YYYY-MM-DD."""
    serializer = TimeSeriesResponseSerializer(
        data={
            "metric": "portfolio_cash_flow",
            "grain": "month",
            "currency": "USD",
            "scale": 1,
            "start": "2026-1-01",
            "end": "2026-01-31",
            "series": [],
            "points": [],
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["start"]


def test_time_series_serializer_rejects_unknown_fields():
    """Dropping strict handling would silently accept misspelled response fields."""
    serializer = TimeSeriesResponseSerializer(
        data={
            "metric": "portfolio_cash_flow",
            "grain": "month",
            "currency": "USD",
            "scale": 1,
            "start": "2026-01-01",
            "end": "2026-01-31",
            "series": [],
            "points": [],
            "unexpected": True,
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["unexpected"]


def test_category_value_serializer_covers_typed_contract_and_strict_fields():
    """Changing category fields would break typed category payloads or hide typos."""
    assert CategoryValueSerializer(CategoryValue("rent", "Rent", "900.00")).data == {
        "key": "rent",
        "label": "Rent",
        "value": "900.00",
    }

    serializer = CategoryValueSerializer(
        data={"key": "rent", "label": "Rent", "value": "900.00", "extra": 1}
    )
    assert not serializer.is_valid()
    assert serializer.errors["extra"]
