"""DRF serializers for the rentals API (Task 16).

These serializers back the new ``/api/v1/`` endpoints (Task 17) and live
in ``rentals.api.serializers``. They are deliberately separate from the
inline ``ModelSerializer`` classes defined in ``rentals/views.py`` (~lines
23-58) which the template views still depend on; Phase 3 will retire
those inline ones.

One ``ModelSerializer`` per user-facing entity (Property, Tenant,
Transaction, FX) plus a non-model ``ChartDataResponseSerializer`` for the
chart-data endpoint. Field lists match the real model fields in
``rentals/models.py`` (no invented fields).
"""

from rest_framework import serializers

from rentals.models import (
    FX,
    Property,
    Property_capital_structure,
    Tenant,
    Transaction,
    User,
)


class PropertySerializer(serializers.ModelSerializer):
    """Serializer for the ``Property`` model.

    Exposes every user-facing field on the model. ``owned_by`` is the FK
    to ``Landlord`` (the landlord's PK); it is writable so the view layer
    can set the owner on create.
    """

    class Meta:
        model = Property
        fields = [
            "id",
            "owned_by",
            "name",
            "location",
            "address",
            "num_bedrooms",
            "area",
            "currency",
            "sold",
        ]


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for the ``Tenant`` model.

    Exposes every user-facing field. ``property`` is the FK to the
    ``Property`` the tenant lives in; ``user`` is the optional linked
    auth user (nullable on the model).
    """

    class Meta:
        model = Tenant
        fields = [
            "id",
            "user",
            "property",
            "first_name",
            "last_name",
            "phone",
            "email",
            "lease_start",
            "payday",
            "lease_end",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for the ``Transaction`` model.

    ``type`` is derived from ``category`` inside ``Transaction.save`` (see
    ``rentals/models.py``), so it is exposed as read-only here to keep
    clients from setting it directly. ``amount`` sign is also normalized
    on save (income positive, expense negative).
    """

    type = serializers.ReadOnlyField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "date",
            "property",
            "tenant",
            "category",
            "period",
            "currency",
            "amount",
            "type",
            "comment",
        ]


class FXSerializer(serializers.ModelSerializer):
    """Serializer for the ``FX`` model (long format, one row per pair)."""

    class Meta:
        model = FX
        fields = [
            "id",
            "date",
            "from_currency",
            "to_currency",
            "rate",
        ]


class PropertyCapitalStructureSerializer(serializers.ModelSerializer):
    """Serializer for the ``Property_capital_structure`` model (Task 5).

    Backs the ``/api/v1/property-valuations/`` ViewSet — the last CRUD
    endpoint needed to retire the legacy ``handle_element`` view (which
    currently handles ``data_type='propertyValuation'``). Field names
    match the model definition in ``rentals/models.py`` (line ~123).
    """

    class Meta:
        model = Property_capital_structure
        fields = [
            "id",
            "property",
            "capital_structure_date",
            "capital_structure_value",
            "capital_structure_debt",
        ]


class ChartDataResponseSerializer(serializers.Serializer):
    """Serializer for the chart-data endpoint response (Task 17).

    Non-model serializer. Shape mirrors what
    ``rentals.services.charts.get_chart_data`` returns:
    ``{"labels": [...], "datasets": [...], "currency": "USD"}``.
    """

    labels = serializers.ListField(child=serializers.CharField(), required=False)
    datasets = serializers.ListField(child=serializers.DictField(), required=False)
    currency = serializers.CharField(required=False)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the ``User`` model (Task 4 — auth endpoints).

    Field list matches the real ``User`` model in ``rentals/models.py``
    and the TypeScript ``User`` type in
    ``frontend/src/types/user.ts``. The boolean toggle on the model is
    named ``use_default_currency_for_all_data`` (the plan originally
    mis-named it ``default_currency_for_all_data``); the corrected name
    is used here.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_landlord",
            "is_tenant",
            "effective_date",
            "default_currency",
            "use_default_currency_for_all_data",
            "chart_frequency",
            "chart_timeline",
            "digits",
        ]
