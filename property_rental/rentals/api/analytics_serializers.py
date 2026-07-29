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
