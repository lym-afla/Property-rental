"""Strict DRF serializers for analytics response contracts."""

from collections.abc import Mapping

from rest_framework import serializers

from rentals.analytics.filters import Grain, ISODateField


class StrictSerializer(serializers.Serializer):
    """Reject undeclared response fields instead of silently discarding them."""

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: ["Unknown field."] for key in sorted(unknown)}
            )
        return super().to_internal_value(data)


class SeriesDefinitionSerializer(StrictSerializer):
    key = serializers.CharField()
    label = serializers.CharField()
    kind = serializers.CharField()


class TimeSeriesPointSerializer(StrictSerializer):
    period_start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    period_end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])

    def to_internal_value(self, data):
        values = serializers.Serializer.to_internal_value(self, data)
        values.update(
            (key, value) for key, value in data.items() if key not in self.fields
        )
        return values

    def to_representation(self, instance):
        values = serializers.Serializer.to_representation(self, instance)
        if isinstance(instance, Mapping):
            dynamic_values = (
                (key, value)
                for key, value in instance.items()
                if key not in self.fields
            )
        else:
            dynamic_values = instance.values.items()
        values.update(dynamic_values)
        return values


class CategoryValueSerializer(StrictSerializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.JSONField()


class TimeSeriesResponseSerializer(StrictSerializer):
    metric = serializers.CharField()
    grain = serializers.ChoiceField(choices=[grain.value for grain in Grain])
    currency = serializers.RegexField(
        r"^[A-Z]{3}$", allow_null=True, required=True
    )
    scale = serializers.IntegerField(min_value=1, max_value=1)
    start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    series = SeriesDefinitionSerializer(many=True)
    points = TimeSeriesPointSerializer(many=True)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        allowed_keys = {"period_start", "period_end"}
        allowed_keys.update(series["key"] for series in representation["series"])
        representation["points"] = [
            {key: value for key, value in point.items() if key in allowed_keys}
            for point in representation["points"]
        ]
        return representation

    def validate(self, attrs):
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError(
                {"end": "end must be on or after start"}
            )
        series_keys = {series["key"] for series in attrs["series"]}
        boundary_keys = {"period_start", "period_end"}
        for index, point in enumerate(attrs["points"]):
            unknown = set(point) - boundary_keys - series_keys
            if unknown:
                raise serializers.ValidationError(
                    {
                        "points": {
                            index: {
                                key: ["Unknown series key."] for key in sorted(unknown)
                            }
                        }
                    }
                )
            if point["period_end"] < point["period_start"]:
                raise serializers.ValidationError(
                    {
                        "points": {
                            index: {
                                "period_end": ["Must be on or after period_start."]
                            }
                        }
                    }
                )
        return attrs


class PortfolioSummarySerializer(StrictSerializer):
    currency = serializers.RegexField(r"^[A-Z]{3}$")
    scale = serializers.IntegerField(min_value=1, max_value=1)
    start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    property_count = serializers.IntegerField(min_value=0)
    rental_inventory_count = serializers.IntegerField(min_value=0)
    occupied = serializers.IntegerField(min_value=0)
    occupancy_rate = serializers.FloatField(min_value=0, max_value=100)
    revenue = serializers.FloatField()
    costs = serializers.FloatField(min_value=0)
    net_income = serializers.FloatField()
    property_value = serializers.FloatField(allow_null=True)
    debt = serializers.FloatField(allow_null=True)
    equity = serializers.FloatField(allow_null=True)
    valuation_status = serializers.ChoiceField(
        choices=[
            "ok",
            "stale_valuation",
            "partial_valuation",
            "missing_valuation",
            "missing_currency",
        ]
    )
    property_value_status = serializers.ChoiceField(
        choices=["ok", "stale_valuation", "missing_valuation", "missing_currency"]
    )
    debt_status = serializers.ChoiceField(
        choices=["ok", "stale_valuation", "missing_valuation", "missing_currency"]
    )


class ContributionRowSerializer(StrictSerializer):
    property_id = serializers.IntegerField(min_value=1)
    property_name = serializers.CharField()
    revenue = serializers.FloatField()
    costs = serializers.FloatField(min_value=0)
    net_income = serializers.FloatField()
    portfolio_share = serializers.FloatField(allow_null=True)


class ContributionResponseSerializer(StrictSerializer):
    metric = serializers.ChoiceField(choices=["property_contribution"])
    currency = serializers.RegexField(r"^[A-Z]{3}$")
    scale = serializers.IntegerField(min_value=1, max_value=1)
    start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    portfolio_net_income = serializers.FloatField()
    rows = ContributionRowSerializer(many=True)


class YieldRowSerializer(StrictSerializer):
    property_id = serializers.IntegerField(min_value=1)
    property_name = serializers.CharField()
    valuation_date = ISODateField(
        format="%Y-%m-%d", input_formats=["%Y-%m-%d"], allow_null=True
    )
    property_value = serializers.FloatField(allow_null=True)
    annualized_revenue = serializers.FloatField(allow_null=True)
    annualized_costs = serializers.FloatField(allow_null=True)
    gross_yield = serializers.FloatField(allow_null=True)
    net_yield = serializers.FloatField(allow_null=True)
    status = serializers.ChoiceField(
        choices=[
            "ok",
            "stale_valuation",
            "missing_valuation",
            "missing_currency",
            "zero_valuation",
            "negative_valuation",
        ]
    )


class YieldResponseSerializer(StrictSerializer):
    metric = serializers.ChoiceField(choices=["property_yields"])
    currency = serializers.RegexField(r"^[A-Z]{3}$")
    scale = serializers.IntegerField(min_value=1, max_value=1)
    start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    rows = YieldRowSerializer(many=True)


class ExposureCoverageSerializer(StrictSerializer):
    period_start = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    period_end = ISODateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    currency = serializers.RegexField(r"^[A-Z]{3}$", allow_null=True)
    status = serializers.ChoiceField(
        choices=[
            "ok",
            "stale_valuation",
            "partial_valuation",
            "partial_stale_valuation",
            "missing_valuation",
            "missing_currency",
            "no_exposure",
        ]
    )
    missing_count = serializers.IntegerField(min_value=0)
    stale_count = serializers.IntegerField(min_value=0)


class CurrencyExposureResponseSerializer(TimeSeriesResponseSerializer):
    metric = serializers.ChoiceField(choices=["currency_exposure"])
    measure = serializers.ChoiceField(
        choices=["property_value", "debt", "rental_income"]
    )
    measure_label = serializers.CharField()
    coverage = ExposureCoverageSerializer(many=True)
