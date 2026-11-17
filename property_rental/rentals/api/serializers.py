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

from copy import copy
from decimal import Decimal

from rest_framework import serializers
from django.conf import settings
from django.core.exceptions import ValidationError as ModelValidationError


from rentals.models import (
    FX,
    DepositMovement,
    Lease_rent,
    Loan,
    LoanCapitalisedFee,
    LoanProduct,
    Property,
    Property_capital_structure,
    Tenant,
    Transaction,
    User,
)

class ValidatedModelSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        instance = self.Meta.model() if self.instance is None else copy(self.instance)
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class PropertySerializer(ValidatedModelSerializer):
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


class TransactionSerializer(ValidatedModelSerializer):
    """Serializer for the ``Transaction`` model.

    ``type`` is derived from ``category`` inside ``Transaction.save`` (see
    ``rentals/models.py``), so it is exposed as read-only here to keep
    clients from setting it directly. ``amount`` sign is also normalized
    on save (income and reimbursements positive; other expenses negative).
    """

    type = serializers.ReadOnlyField()
    # Reverse one-to-one from ``DepositMovement.transaction``: the movement
    # PK, or ``null`` for a transaction not linked to a security deposit.
    deposit_movement = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)

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
            "deposit_movement",
            "loan",
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


class PropertyCapitalStructureSerializer(ValidatedModelSerializer):
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
            "loan",
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


class DepositMovementSerializer(serializers.ModelSerializer):
    """Serializer for ``DepositMovement`` (``/api/v1/deposit-movements/``).

    Plain field validation only: ``kind`` / ``applied_to`` are restricted
    to their model choices so bad values are 400s. Business rules and
    ownership checks live in ``services.deposits`` and the ViewSet.
    ``owns_transaction`` is read-only (set by the service).
    """

    class Meta:
        model = DepositMovement
        fields = [
            "id",
            "tenant",
            "date",
            "kind",
            "currency",
            "amount",
            "applied_to",
            "transaction",
            "owns_transaction",
            "comment",
        ]
        read_only_fields = ["owns_transaction"]
        # Drop the auto OneToOne UniqueValidator on ``transaction``: it runs
        # before the ownership check and would reveal whether another
        # landlord's transaction is deposit-linked. The service rejects
        # double-linking on field ``transaction``.
        extra_kwargs = {
            "applied_to": {"allow_blank": False},
            "transaction": {"validators": []},
        }


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


class LoanSerializer(ValidatedModelSerializer):
    class Meta:
        model = Loan
        fields = ["id", "property", "lender", "currency", "reference", "start_date",
                  "end_date", "original_principal", "interest_rate", "rate_type",
                  "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class LoanProductFilterSerializer(serializers.Serializer):
    loan = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)
    property = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)


class LoanProductSerializer(ValidatedModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ["id", "loan", "name", "lender", "start_date", "end_date", "interest_rate",
                  "rate_type", "opening_balance", "notes", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        self.fields["loan"].queryset = Loan.objects.filter(property__owned_by__user=request.user) if request else Loan.objects.none()

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)


class LoanCapitalisedFeeFilterSerializer(serializers.Serializer):
    loan = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)
    property = serializers.IntegerField(required=False, min_value=1, max_value=2**63 - 1)


class LoanCapitalisedFeeSerializer(ValidatedModelSerializer):
    class Meta:
        model = LoanCapitalisedFee
        fields = ["id", "loan", "property", "date", "amount", "description", "created_at", "updated_at"]
        read_only_fields = ["property", "created_at", "updated_at"]


class LoanPaymentSerializer(serializers.Serializer):
    date = serializers.DateField()
    interest = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"))
    total = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False)
    principal = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0"), required=False)
    comment = serializers.CharField(max_length=250, required=False, allow_blank=True)
    period = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate(self, attrs):
        if ("total" in attrs) == ("principal" in attrs):
            raise serializers.ValidationError("Supply total and interest, or interest and principal.")
        if "total" in attrs:
            attrs["principal"] = attrs.pop("total") - attrs["interest"]
            if attrs["principal"] < 0:
                raise serializers.ValidationError({"total": "Must be at least the interest."})
        if attrs["principal"] + attrs["interest"] <= 0:
            raise serializers.ValidationError("The payment must be positive.")
        return attrs
