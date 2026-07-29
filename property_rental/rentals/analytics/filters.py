"""Validation and normalization of analytics URL query parameters."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from rest_framework import serializers


class Grain(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class _AnalyticsFilterSerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    grain = serializers.ChoiceField(
        choices=[grain.value for grain in Grain], required=False
    )
    currency = serializers.RegexField(r"^[A-Z]{3}$", required=False)
    comparison = serializers.CharField(required=False, allow_blank=False)
    property = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )


@dataclass(frozen=True)
class AnalyticsFilters:
    start: date
    end: date
    grain: Grain
    currency: str
    comparison: str | None
    property_ids: tuple[int, ...]

    @classmethod
    def from_query_params(
        cls, params, default_currency: str, effective_date: date
    ) -> "AnalyticsFilters":
        """Parse URL query state into a validated, immutable filter value."""
        raw = {
            key: params.get(key)
            for key in ("start", "end", "grain", "currency", "comparison")
            if key in params
        }
        if "currency" in raw:
            raw["currency"] = raw["currency"].upper()
        if "property" in params:
            raw["property"] = params.getlist("property")

        serializer = _AnalyticsFilterSerializer(data=raw)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data

        end = values.get("end", effective_date)
        start = values.get("start", end.replace(month=1, day=1))
        if end < start:
            raise serializers.ValidationError(
                {"end": "end must be on or after start"}
            )

        currency = values.get("currency", (default_currency or "").upper())
        if len(currency) != 3 or not currency.isalpha():
            raise serializers.ValidationError(
                {"currency": "currency must be a three-letter code"}
            )

        return cls(
            start=start,
            end=end,
            grain=Grain(values.get("grain", Grain.MONTH.value)),
            currency=currency,
            comparison=values.get("comparison"),
            property_ids=tuple(values.get("property", ())),
        )
