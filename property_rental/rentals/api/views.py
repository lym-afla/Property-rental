"""DRF ViewSets and the ``ChartDataView`` APIView for ``/api/v1/`` (Task 17).

This module wires the four user-facing entities (Property, Tenant,
Transaction, FX) as :class:`rest_framework.viewsets.ModelViewSet`
subclasses and adds a single :class:`ChartDataView` :class:`APIView` for
the chart-data endpoint that the React frontend (Phase 2) consumes.

Security model (the central concern of this task)
-------------------------------------------------
The Task-16 serializers deliberately expose the ownership FKs
(``owned_by`` / ``property`` / ``tenant`` / ``user``) as writable. That
makes an IDOR possible *at the serializer layer*: a client could POST a
Tenant pointing at another landlord's ``property`` and silently hijack a
row. This module makes that class of bug **structurally impossible** at
the API layer via two complements:

1. **Per-user queryset scoping.** Every ViewSet overrides
   :meth:`get_queryset` so LIST and RETRIEVE only ever see rows whose
   ownership path leads back to ``request.user``. An out-of-scope PK
   simply does not exist from the caller's perspective (404, not 403 —
   no enumeration channel).

2. **Ownership forcing on create.** Each ViewSet overrides
   :meth:`perform_create` (and :meth:`perform_update`) to either force
   the ownership FK to the requester (Property) or validate that the
   client-supplied FK (Tenant/Transaction's ``property`` and
   Transaction's ``tenant``) belongs to the requester before saving.

Combined with ``permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]``
(object-level owner checks behind the global auth gate), the API layer
cannot leak or accept cross-tenant data even if a future serializer
change widens a field.

Query param naming for ``ChartDataView``
----------------------------------------
The query string follows the **session-key reality** the existing
template views established in Task 12's bug fix
(``test_property_valuation_uses_request_params``):
``freq`` / ``start`` / ``end`` / ``currency`` (not ``frequency`` /
``from`` / ``to``). The translation into
:func:`services.charts.get_chart_data`'s positional signature
``(type, element_id, frequency, from_date, to_date, currency, ...)``
happens inside the view.
"""

from datetime import date

from dateutil.parser import parse as parse_date

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from rentals.models import FX, Landlord, Property, Property_capital_structure, Tenant, Transaction
from rentals.services.charts import get_chart_data as _get_chart_data

from .permissions import IsOwnerOrReadOnly
from .serializers import (
    ChartDataResponseSerializer,
    FXSerializer,
    PropertyCapitalStructureSerializer,
    PropertySerializer,
    TenantSerializer,
    TransactionSerializer,
)


# ``IsAuthenticated`` must be paired with ``IsOwnerOrReadOnly`` on every
# ViewSet: ``IsOwnerOrReadOnly`` only defines ``has_object_permission``
# (object-level checks), so on its own its ``has_permission`` falls through
# to the default True — which would let anonymous users reach
# ``get_queryset()`` and crash on ``request.user`` lookups. Pairing the two
# keeps the global gate (IsAuthenticated) AND the per-object owner check
# (IsOwnerOrReadOnly) active together.
_OWNER_PERMS = [IsAuthenticated, IsOwnerOrReadOnly]


# ---------------------------------------------------------------------------
# Per-user scoping helpers
# ---------------------------------------------------------------------------


def _validate_property_owned_by(property_id, user):
    """Resolve a Property PK to an owned instance or raise DRF NotFound.

    Used by the Tenant/Transaction ViewSets to validate the
    client-supplied ``property`` FK before save — failing with 404 (the
    property doesn't exist *from this caller's perspective*) rather than
    silently creating a cross-tenant record.
    """
    qs = Property.objects.filter(id=property_id, owned_by__user=user)
    return get_object_or_404(qs)


def _parse_as_of(query_params):
    """Pull ``as_of`` from the query string and return a ``date``.

    Accepts ``YYYY-MM-DD`` (or anything ``dateutil`` can parse). Falls
    back to ``date.today()`` when the param is missing or unparseable.
    Used by the ``with_stats`` actions below.
    """
    as_of_str = query_params.get("as_of")
    if not as_of_str:
        return date.today()
    try:
        return parse_date(as_of_str).date()
    except (ValueError, TypeError, OverflowError):
        return date.today()


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------


class PropertyViewSet(viewsets.ModelViewSet):
    """CRUD for Property scoped to ``request.user.landlord``.

    * ``get_queryset`` — only this landlord's properties.
    * ``perform_create`` / ``perform_update`` — force ``owned_by`` to the
      requesting landlord, ignoring any client-supplied value (IDOR fix).
    """

    serializer_class = PropertySerializer
    permission_classes = _OWNER_PERMS

    def get_queryset(self):
        return Property.objects.filter(owned_by__user=self.request.user)

    def _force_owner(self, serializer):
        """Persist a Property pinned to the requesting landlord.

        ``owned_by`` is read off the requester's Landlord, regardless of
        what the client sent — this is the structural IDOR fix. If the
        authenticated user has no Landlord (e.g. a tenant-role user),
        return 403 rather than letting the ``Landlord.DoesNotExist``
        propagate as a 500.
        """
        try:
            landlord = self.request.user.landlord
        except Landlord.DoesNotExist:
            raise PermissionDenied("Only landlords can create properties.")
        serializer.save(owned_by=landlord)

    def perform_create(self, serializer):
        self._force_owner(serializer)

    def perform_update(self, serializer):
        self._force_owner(serializer)

    @action(detail=False, methods=["get"])
    def with_stats(self, request):
        """GET /api/v1/properties/with_stats/?as_of=YYYY-MM-DD&currency=USD

        Returns this landlord's properties augmented with per-property
        P&L aggregates (income / expense / net, both all-time and
        year-to-date) in ``currency`` as of ``as_of``. The aggregates
        are computed by the financial-aggregation service
        (:func:`rentals.services.financials.aggregate`) via the
        :meth:`Transaction.financials` delegate — same code path the
        legacy ``table_data`` view used, so the math is identical.

        Returned shape (one entry per owned property)::

            {
              ...PropertySerializer fields,        # ``currency`` is the NATIVE
                                                    # property currency (RUB/GBP/
                                                    # etc.) — used by the frontend
                                                    # for the Currency Exposure
                                                    # chart grouping.
              "gross_income_all_time": float,
              "expenses_all_time": float,        # always <= 0
              "net_income_all_time": float,      # income + expense
              "gross_income_ytd": float,
              "expenses_ytd": float,
              "net_income_ytd": float,
              "stats_currency": "USD"             # currency the aggregates are
                                                    # FX-converted into (defaults
                                                    # to ``USD``).
            }

        Expenses carry their negative sign through from the underlying
        ``Transaction.amount`` (income positive, expense negative on
        save) — ``net = income + expense`` is therefore income minus
        the absolute expense, matching what the legacy
        ``handle_element`` view rendered.
        """
        # Lazy import: ``services.financials`` references ``rentals.models``
        # lazily at call time but avoids an import-time cycle by deferring
        # the model import — this side of the boundary imports cleanly at
        # module load, but the lazy pattern matches the rest of the API
        # layer (and is cheaper to reason about if the services module's
        # import graph changes later).
        from rentals.services.financials import aggregate

        as_of = _parse_as_of(request.query_params)
        currency = request.query_params.get("currency", "USD")
        year_start = date(as_of.year, 1, 1)
        year_end = date(as_of.year, 12, 31)

        properties = self.get_queryset()
        result = []
        for prop in properties:
            gross_income_all = aggregate(
                Transaction,
                end_date=as_of,
                target_currency=currency,
                properties=[prop],
                transaction_type="income",
            )
            expenses_all = aggregate(
                Transaction,
                end_date=as_of,
                target_currency=currency,
                properties=[prop],
                transaction_type="expense",
            )
            gross_income_ytd = aggregate(
                Transaction,
                end_date=year_end,
                start_date=year_start,
                target_currency=currency,
                properties=[prop],
                transaction_type="income",
            )
            expenses_ytd = aggregate(
                Transaction,
                end_date=year_end,
                start_date=year_start,
                target_currency=currency,
                properties=[prop],
                transaction_type="expense",
            )

            data = PropertySerializer(prop).data
            # Preserve the property's native ``currency`` (RUB/GBP/etc.) so
            # the frontend can group by it for the Currency Exposure chart.
            # The FX-converted currency the aggregates are denominated in
            # is exposed separately as ``stats_currency`` (almost always
            # ``USD``) — previously this view overwrote ``currency`` with
            # the target currency, which collapsed every property to USD
            # in the exposure chart.
            data.update(
                {
                    "gross_income_all_time": float(gross_income_all),
                    "expenses_all_time": float(expenses_all),
                    "net_income_all_time": float(gross_income_all + expenses_all),
                    "gross_income_ytd": float(gross_income_ytd),
                    "expenses_ytd": float(expenses_ytd),
                    "net_income_ytd": float(gross_income_ytd + expenses_ytd),
                    "stats_currency": currency,
                }
            )
            result.append(data)
        return Response(result)


class TenantViewSet(viewsets.ModelViewSet):
    """CRUD for Tenant scoped via ``property.owned_by.user``.

    * ``get_queryset`` — only tenants in properties owned by this user.
    * ``perform_create`` / ``perform_update`` — validate the
      client-supplied ``property`` belongs to the requester before save
      (404 otherwise), preventing cross-landlord Tenant injection.
    """

    serializer_class = TenantSerializer
    permission_classes = _OWNER_PERMS

    def get_queryset(self):
        return Tenant.objects.filter(property__owned_by__user=self.request.user)

    def _validate_and_save(self, serializer):
        """Validate ``property`` ownership, then save the Tenant.

        ``Tenant.user`` is an optional link to a tenant auth account. We
        do NOT let the client reassign it (left as whatever the serializer
        produces from the payload, but if a tenant FK is supplied via
        another endpoint that path is also scoped). The critical check
        here is ``property`` — it determines which landlord the row is
        visible to.

        On PATCH (partial update) the client may omit ``property`` because
        it is unchanged. In that case fall back to the existing instance's
        ``property`` — DRF's ``PrimaryKeyRelatedField`` resolves the FK to
        a ``Property`` model instance, not an id, so ``property_obj`` is
        the appropriate name. On create, ``property`` is required by the
        serializer and will always be present in ``validated_data``.
        """
        property_obj = serializer.validated_data.get("property") or getattr(
            serializer.instance, "property", None
        )
        if property_obj is None:
            # Create path with a missing required field — the serializer
            # should already have raised 400, but defend against fall-through.
            raise ValidationError({"property": "This field is required."})
        # Resolve via the user-scoped queryset — raises 404 if the
        # property belongs to another landlord (defeating enumeration).
        _validate_property_owned_by(property_obj.id, self.request.user)
        serializer.save()

    def perform_create(self, serializer):
        self._validate_and_save(serializer)

    def perform_update(self, serializer):
        self._validate_and_save(serializer)

    @action(detail=False, methods=["get"])
    def with_stats(self, request):
        """GET /api/v1/tenants/with_stats/?as_of=YYYY-MM-DD&currency=USD

        Returns this landlord's tenants augmented with per-tenant rent
        aggregates:

        * ``rent_rate`` — the tenant's current monthly lease rent as of
          ``as_of`` (or the string status ``"Tenant vacated"`` /
          ``"No rent history for the Tenant"`` from
          :meth:`Tenant.lease_rent`).
        * ``revenue_all_time`` — total rent collected for this tenant
          (lease-start through ``as_of``, including post-vacation
          payments).
        * ``revenue_ytd`` — same, year-to-date window.
        * ``debt`` — :meth:`Tenant.debt` (paid - due; negative => the
          tenant is in arrears) as of ``as_of``.

        All monetary aggregates are FX-converted into ``currency`` via
        :meth:`Tenant.rent_total` (which itself delegates to
        :func:`rentals.services.financials.convert_transactions` when the
        tenant's property currency differs). ``debt`` is computed in the
        tenant's property currency and converted via the FX service at
        the request date.

        Returned shape (one entry per owned tenant)::

            {
              ...TenantSerializer fields,
              "rent_rate": float | str,
              "revenue_all_time": float,
              "revenue_ytd": float,
              "debt": float,
              "stats_currency": "USD"            # currency the aggregates are
                                                  # FX-converted into (defaults
                                                  # to ``USD``). The tenant's
                                                  # native currency is the
                                                  # property's ``currency``.
            }
        """
        # Lazy import matches PropertyViewSet.with_stats.
        from rentals.services import fx as fx_service

        as_of = _parse_as_of(request.query_params)
        currency = request.query_params.get("currency", "USD")
        year_start = date(as_of.year, 1, 1)
        year_end = date(as_of.year, 12, 31)

        tenants = self.get_queryset()
        result = []
        for tenant in tenants:
            lease_rent = tenant.lease_rent(as_of)
            revenue_all_time = tenant.rent_total(
                as_of,
                target_currency=currency,
                include_post_vacation=True,
            )
            revenue_ytd = tenant.rent_total(
                start_date=year_start,
                end_date=year_end,
                target_currency=currency,
                include_post_vacation=True,
            )
            debt_value = tenant.debt(as_of)
            # ``debt`` is denominated in the tenant's property currency
            # (rent_total inside ``scheduler.debt`` short-circuits to
            # face value when ``target_currency`` is None — the property
            # currency path). Convert into the requested currency here
            # so the field matches the revenue fields.
            debt_converted = fx_service.convert(
                debt_value,
                tenant.property.currency,
                currency,
                as_of,
            )

            rent_rate = (
                lease_rent
                if isinstance(lease_rent, str)
                else float(lease_rent)
            )

            data = TenantSerializer(tenant).data
            data.update(
                {
                    "rent_rate": rent_rate,
                    "revenue_all_time": float(revenue_all_time),
                    "revenue_ytd": float(revenue_ytd),
                    "debt": float(debt_converted),
                    "stats_currency": currency,
                }
            )
            result.append(data)
        return Response(result)

    @action(detail=True, methods=["post"])
    def vacate(self, request, pk=None):
        """POST /api/v1/tenants/<id>/vacate/ body ``{lease_end}`` -> 200
        serialized tenant.

        Sets ``lease_end`` on a tenant. Ownership is enforced by
        :meth:`get_object`, which uses the same per-user scoped queryset
        as LIST / RETRIEVE — so a tenant owned by another landlord
        resolves to a 404 (no enumeration channel), exactly mirroring the
        rest of the API's isolation model. A missing ``lease_end`` is a
        400 field-level error.
        """
        tenant = self.get_object()  # ownership-scoped (404 on mismatch)
        lease_end = request.data.get("lease_end")
        if not lease_end:
            return Response(
                {"lease_end": "This field is required."},
                status=400,
            )
        tenant.lease_end = lease_end
        tenant.save()
        return Response(TenantSerializer(tenant).data, status=200)


class TransactionViewSet(viewsets.ModelViewSet):
    """CRUD for Transaction scoped via ``property.owned_by.user``.

    Transaction has TWO FKs that must be validated against the requester:

    * ``property`` — must belong to the requesting user (else 404).
    * ``tenant`` (nullable) — if supplied, must belong to a Property the
      requesting user owns.

    Both are checked before save; a mismatch raises ``ValidationError``
    (400). The two-FK validation is the subtle case the brief calls out:
    a client could POST a Transaction with their own ``property`` PK and
    another landlord's ``tenant`` PK, silently creating a cross-tenant
    link. The check below catches that exact pattern.
    """

    serializer_class = TransactionSerializer
    permission_classes = _OWNER_PERMS

    def get_queryset(self):
        return Transaction.objects.filter(property__owned_by__user=self.request.user)

    def _validate_and_save(self, serializer):
        # Validate ``property`` ownership via the scoped queryset (404).
        # On PATCH (partial update) the client may omit ``property``
        # because it is unchanged; fall back to the existing instance.
        # DRF's ``PrimaryKeyRelatedField`` resolves the FK to a model
        # instance, not an id.
        property_obj = serializer.validated_data.get("property") or getattr(
            serializer.instance, "property", None
        )
        if property_obj is None:
            raise ValidationError({"property": "This field is required."})
        _validate_property_owned_by(property_obj.id, self.request.user)

        # Validate ``tenant`` ownership if supplied. A client could point
        # a Transaction at their own property but another landlord's
        # tenant (the cross-tenant hijack the brief flags). Catch it here
        # by re-using the user-scoped tenant queryset. On PATCH, fall
        # back to the existing instance's ``tenant`` so a partial update
        # that omits ``tenant`` does not skip the check on a previously
        # cross-tenant value.
        tenant_obj = serializer.validated_data.get("tenant")
        if tenant_obj is None and serializer.instance is not None:
            # ``tenant`` is nullable; only fall back when an instance
            # already has one (so we re-validate the pre-existing link).
            tenant_obj = getattr(serializer.instance, "tenant", None)
        if tenant_obj is not None:
            tenant_qs = Tenant.objects.filter(
                id=tenant_obj.id, property__owned_by__user=self.request.user
            )
            if not tenant_qs.exists():
                # 400 (not 404) so the client gets a clear field-level
                # error pointing at ``tenant``.
                raise ValidationError({"tenant": "Tenant does not belong to a property you own."})

        serializer.save()

    def perform_create(self, serializer):
        self._validate_and_save(serializer)

    def perform_update(self, serializer):
        self._validate_and_save(serializer)


class FXViewSet(viewsets.ModelViewSet):
    """CRUD for FX rows.

    FX rows are not scoped to a landlord (FX is a shared reference-table
    in this app — every landlord reads the same currency-pair rates). So
    only ``IsAuthenticated`` is applied here — there is no per-user
    ownership to enforce. Writes are left open to authenticated landlords
    to match the existing ``fx_list`` template view's behavior (Phase 3
    may tighten this if FX editing moves entirely to a server-side job).
    """

    serializer_class = FXSerializer
    permission_classes = [IsAuthenticated]
    queryset = FX.objects.all()

    @action(detail=False, methods=["post"], url_path="update")
    def update_rates(self, request):
        """POST /api/v1/fx/update/ -> 200 ``{detail: "FX rates updated"}``.

        Wraps :func:`rentals.services.fx.update_rates` (which itself
        wraps the yfinance fetch). ``services.fx.update_rates`` takes a
        single ``property_id`` (NOT a user), so this endpoint mirrors
        the legacy ``update_fx_view`` and loops over the requester's own
        properties, calling the service once per property. Scoping to the
        requester's properties avoids touching other users' data and
        bounds the external yfinance calls.

        The legacy view returned ``{'success': True, ...}``; we return a
        ``{detail: ...}`` shape for consistency with the rest of the
        ``/api/v1/`` namespace. Failures inside the service (e.g.
        yfinance outages) propagate as 500s today, matching the legacy
        view's ``try/except`` path that surfaced the message; a future
        task can wrap this in a structured error envelope.
        """
        from rentals.services.fx import update_rates

        for prop in Property.objects.filter(owned_by__user=request.user):
            update_rates(prop.id)
        return Response({"detail": "FX rates updated"}, status=200)


class PropertyCapitalStructureViewSet(viewsets.ModelViewSet):
    """CRUD for ``Property_capital_structure`` scoped via
    ``property.owned_by.user`` (Task 5).

    This is the last CRUD endpoint needed to retire the legacy
    ``handle_element`` view's ``data_type='propertyValuation'`` branch.

    * ``get_queryset`` — only capital-structure rows whose ``property`` is
      owned by the requesting user.
    * ``perform_create`` / ``perform_update`` — validate the
      client-supplied ``property`` FK belongs to the requester before
      save, preventing cross-landlord capital-structure injection (the
      same IDOR class of bug the Tenant/Transaction ViewSets defend
      against). The check uses ``request.data`` (the raw payload) so it
      fires even before the serializer would resolve the FK.
    """

    serializer_class = PropertyCapitalStructureSerializer
    permission_classes = _OWNER_PERMS

    def get_queryset(self):
        return Property_capital_structure.objects.filter(
            property__owned_by__user=self.request.user
        )

    def perform_create(self, serializer):
        # Validate the property belongs to the requester before saving.
        property_id = self.request.data.get('property')
        if not Property.objects.filter(
            id=property_id, owned_by__user=self.request.user
        ).exists():
            raise ValidationError(
                {"property": "This property does not belong to you."}
            )
        serializer.save()

    def perform_update(self, serializer):
        # Same ownership check on the property FK if it's being changed.
        property_id = self.request.data.get('property')
        if property_id is not None:
            if not Property.objects.filter(
                id=property_id, owned_by__user=self.request.user
            ).exists():
                raise ValidationError(
                    {"property": "This property does not belong to you."}
                )
        serializer.save()


# ---------------------------------------------------------------------------
# ChartDataView
# ---------------------------------------------------------------------------


class ChartDataView(APIView):
    """GET /api/v1/chart-data/?type=...&id=...&freq=...&start=...&end=...&currency=...

    Bridges the existing :func:`rentals.services.charts.get_chart_data`
    service into the new ``/api/v1/`` namespace. The query-string keys
    match the session-key reality from Task 12
    (``freq``/``start``/``end``/``currency``); the translation into
    ``get_chart_data``'s positional signature happens here.

    Ownership is validated for the referenced entity:

    * ``type=property`` — the property must be owned by the requester.
    * ``type=tenant`` — the tenant's property must be owned by the
      requester.
    * ``type=homePage`` — no entity to validate (operates on the
      requester's own property set by default).

    A cross-landlord reference returns 404 (no enumeration channel).
    """

    def get(self, request, *args, **kwargs):
        chart_type = request.GET.get("type")
        element_id = request.GET.get("id")
        frequency = request.GET.get("freq")
        from_date = request.GET.get("start")
        to_date = request.GET.get("end")
        currency = request.GET.get("currency")

        if not chart_type or not frequency or not from_date or not to_date:
            return Response(
                {"detail": "type, freq, start, end are required query params."},
                status=400,
            )

        properties = None

        if chart_type == "property":
            # Resolve via the scoped queryset so an out-of-scope PK 404s.
            property_obj = get_object_or_404(
                Property.objects.filter(id=element_id, owned_by__user=request.user)
            )
            if currency is None:
                currency = property_obj.currency
        elif chart_type == "tenant":
            tenant_obj = get_object_or_404(
                Tenant.objects.filter(id=element_id, property__owned_by__user=request.user)
            )
            if currency is None:
                currency = tenant_obj.property.currency
        elif chart_type == "homePage":
            # homePage operates on the caller's own properties — no
            # cross-tenant leak is possible because the property set is
            # always scoped to request.user.
            properties = list(
                Property.objects.filter(owned_by__user=request.user)
            )
            if currency is None:
                currency = request.user.default_currency or "USD"
        else:
            return Response({"detail": f"Unknown chart type: {chart_type!r}."}, status=400)

        chart_data = _get_chart_data(
            chart_type,
            element_id,
            frequency,
            from_date,
            to_date,
            currency,
            properties=properties,
        )

        serializer = ChartDataResponseSerializer(data=chart_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)
