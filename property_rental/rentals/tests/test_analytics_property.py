"""Behavior and API tests for property valuation analytics."""

from datetime import date
from decimal import Decimal

import pytest
from django.http import Http404

from rentals.tests.factories import (
    PropertyCapitalStructureFactory,
    PropertyFactory,
)


@pytest.mark.django_db
def test_valuation_returns_full_history_in_raw_currency(
    landlord_user, sample_property
):
    """Scaling or repeating records would corrupt the valuation history."""
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2018, 4, 2),
        capital_structure_value=Decimal("500000.00"),
        capital_structure_debt=Decimal("200000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 7, 29),
        capital_structure_value=Decimal("650000.00"),
        capital_structure_debt=Decimal("175000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 8, 1),
        capital_structure_value=Decimal("700000.00"),
        capital_structure_debt=Decimal("160000.00"),
    )

    result = property_valuation_history(
        landlord_user, sample_property.id, end=date(2026, 7, 29)
    )

    assert result.currency == sample_property.currency
    assert result.scale == 1
    assert result.start == date(2018, 4, 2)
    assert [point["period_start"] for point in result.points] == [
        date(2018, 4, 2),
        date(2026, 7, 29),
    ]
    assert result.points[0]["period_end"] == date(2018, 4, 2)
    assert result.points[0]["total_value"] == 500000.0
    assert result.points[0]["debt"] == 200000.0
    assert result.points[0]["equity"] == 300000.0


@pytest.mark.django_db
def test_property_valuation_history_interpolates_requested_start(
    landlord_user, sample_property
):
    """A requested date inside two records gets a linearly interpolated point."""
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2020, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2022, 1, 1),
        capital_structure_value=Decimal("200000.00"),
        capital_structure_debt=Decimal("80000.00"),
    )

    result = property_valuation_history(
        landlord_user,
        sample_property.id,
        start=date(2021, 1, 1),
        end=date(2022, 12, 31),
    )

    assert result.start == date(2021, 1, 1)
    assert result.points[0]["period_start"] == date(2021, 1, 1)
    assert result.points[0]["status"] == "interpolated"
    assert result.points[0]["total_value"] == pytest.approx(150000, rel=0.01)
    assert result.points[0]["debt"] == pytest.approx(60000, rel=0.01)
    assert result.points[0]["equity"] == pytest.approx(90000, rel=0.01)
    assert result.points[1]["period_start"] == date(2022, 1, 1)
    assert result.points[1]["status"] == "ok"


@pytest.mark.django_db
def test_property_valuation_history_carries_forward_start_after_last_prior_record(
    landlord_user, sample_property
):
    """A requested date after the latest record uses that record's values."""
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2020, 1, 1),
        capital_structure_value=Decimal("100000.00"),
        capital_structure_debt=Decimal("40000.00"),
    )

    result = property_valuation_history(
        landlord_user,
        sample_property.id,
        start=date(2021, 1, 1),
        end=date(2021, 12, 31),
    )

    assert result.points[0]["period_start"] == date(2021, 1, 1)
    assert result.points[0]["status"] == "carried_forward"
    assert result.points[0]["total_value"] == 100000.0
    assert result.points[0]["debt"] == 40000.0


@pytest.mark.django_db
def test_valuation_preserves_missing_debt_and_equity(
    landlord_user, sample_property
):
    """Coercing absent debt to zero would fabricate both debt and equity."""
    from rentals.analytics.property import property_valuation_history

    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2026, 1, 15),
        capital_structure_value=Decimal("500000.00"),
        capital_structure_debt=None,
    )

    result = property_valuation_history(
        landlord_user, sample_property.id, end=date(2026, 1, 31)
    )

    assert result.status == "partial_valuation"
    assert result.points[0]["total_value"] == 500000.0
    assert result.points[0]["debt"] is None
    assert result.points[0]["equity"] is None
    assert result.points[0]["status"] == "missing_debt"


@pytest.mark.django_db
def test_valuation_returns_explicit_missing_state(landlord_user, sample_property):
    """An empty history must remain distinguishable from a successful data series."""
    from rentals.analytics.property import property_valuation_history

    result = property_valuation_history(
        landlord_user, sample_property.id, end=date(2026, 7, 29)
    )

    assert result.status == "missing_valuation"
    assert result.points == ()
    assert result.start == result.end == date(2026, 7, 29)


@pytest.mark.django_db
def test_valuation_rejects_cross_owner_property(
    landlord_user, other_landlord_user
):
    """Removing scoped lookup would expose another owner's capital history."""
    from rentals.analytics.property import property_valuation_history

    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)

    with pytest.raises(Http404):
        property_valuation_history(
            landlord_user, other_property.id, end=date(2026, 7, 29)
        )


@pytest.mark.django_db
def test_valuation_api_serializes_exact_dates_and_rejects_cross_owner(
    auth_client, sample_property, other_landlord_user
):
    """The HTTP boundary must preserve record dates and ownership isolation."""
    other_property = PropertyFactory(owned_by=other_landlord_user.landlord)
    PropertyCapitalStructureFactory(
        property=sample_property,
        capital_structure_date=date(2020, 2, 3),
        capital_structure_value=Decimal("500000.00"),
        capital_structure_debt=Decimal("200000.00"),
    )

    response = auth_client.get(
        f"/api/v1/analytics/properties/{sample_property.id}/valuation/",
        {"end": "2026-07-29"},
    )
    forbidden = auth_client.get(
        f"/api/v1/analytics/properties/{other_property.id}/valuation/",
        {"end": "2026-07-29"},
    )

    assert response.status_code == 200
    assert response.json()["points"][0] == {
        "period_start": "2020-02-03",
        "period_end": "2020-02-03",
        "total_value": 500000.0,
        "debt": 200000.0,
        "equity": 300000.0,
        "status": "ok",
    }
    assert forbidden.status_code == 404
