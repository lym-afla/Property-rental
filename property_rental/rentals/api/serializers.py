"""DRF serializers for the rentals API (Task 16).

These serializers back the new ``/api/v1/`` endpoints (Task 17) and live
in ``rentals.api.serializers``. They are deliberately separate from the
inline ``ModelSerializer`` classes defined in ``rentals/views.py`` (~lines
23-58) which the template views still depend on; Phase 3 will retire
those inline ones.

One ``ModelSerializer`` per user-facing entity (Property, Tenant,
Transaction and FX. Field lists match the real model fields in
``rentals/models.py`` (no invented fields).
"""

from decimal import Decimal

from rest_framework import serializers
from django.conf import settings

from rentals.models import (
    FX,
    Lease_rent,
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
    on save (income and reimbursements positive; other expenses negative).
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

    def validate(self, attrs):
        if (
            attrs.get("capital_structure_debt") in ("", None)
            and (self.instance is None or "capital_structure_debt" in attrs)
        ):
            attrs["capital_structure_debt"] = Decimal("0")
        return attrs

    class Meta:
        model = Property_capital_structure
        fields = [
            "id",
            "property",
            "capital_structure_date",
            "capital_structure_value",
            "capital_structure_debt",
        ]


class LeaseRentSerializer(serializers.ModelSerializer):
    """Serializer for the ``Lease_rent`` model.

    Backs the ``/api/v1/lease-rents/`` ViewSet — the write path the
    tenant detail page's "Update rent" dialog uses to push a new
    effective-date rent entry (the read path is already covered by
    ``TenantViewSet.with_stats``'s ``rent_rate`` aggregate, which calls
    ``Tenant.lease_rent``).

    Field names mirror the model definition in ``rentals/models.py``:
    ``tenant`` (FK), ``date_rent_set`` (effective date), ``rent``
    (decimal), ``currency`` (the rent's currency, defaults to ``USD``).
    """

    class Meta:
        model = Lease_rent
        fields = [
            "id",
            "tenant",
            "date_rent_set",
            "rent",
            "currency",
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the ``User`` model (Task 4 — auth endpoints).

    Field list matches the real ``User`` model in ``rentals/models.py``
    and the TypeScript ``User`` type in
    ``frontend/src/types/user.ts``. The boolean toggle on the model is
    named ``use_default_currency_for_all_data`` (the plan originally
    mis-named it ``default_currency_for_all_data``); the corrected name
    is used here.

    Phase 4 Task 6 (2026-07-19): ``id``, ``username``, ``is_landlord``
    and ``is_tenant`` are read-only. The ``MeView.patch`` endpoint
    accepts arbitrary user fields via ``partial=True``; without this
    restriction a tenant-role user could escalate to landlord by
    PATCHing ``{"is_landlord": true}``, and any user could move to
    another landlord's account namespace by PATCHing ``{"id": ...}``.
    The role flags and the PK are set ONLY by the registration /
    admin path, never by ``PATCH /auth/me/``.
    """

    def get_fields(self):
        fields = super().get_fields()
        if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
            fields.pop("effective_date", None)
        return fields

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
        read_only_fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_landlord",
            "is_tenant",
        ]
