"""Strict DRF serializers for analytics response contracts."""

from rest_framework import serializers

from rentals.analytics.filters import Grain


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
    date = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    values = serializers.DictField()


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
    start = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    end = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    series = SeriesDefinitionSerializer(many=True)
    points = TimeSeriesPointSerializer(many=True)

    def validate(self, attrs):
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError(
                {"end": "end must be on or after start"}
            )
        return attrs
