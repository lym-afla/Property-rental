"""DRF ViewSets for the ``/api/v1/`` namespace (Task 17).

This module wires the four user-facing entities (Property, Tenant,
Transaction, FX) as :class:`rest_framework.viewsets.ModelViewSet`
subclasses for the user-facing API.

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

"""

from datetime import date

from dateutil.parser import parse as parse_date

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rentals.models import FX, Landlord, Lease_rent, Property, Property_capital_structure, Tenant, Transaction
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    FXSerializer,
    LeaseRentSerializer,
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


def _native_sum(prop, window, transaction_type):
    """Sum a property's transactions at face value (no FX conversion).

    Used by ``PropertyViewSet.with_stats`` when ``currency=native`` (or
    omitted). Each ``Transaction.amount`` is stored in its own currency;
    for a single-property native-currency roll-up the per-row currency
    is the property currency in practice, so a plain SQL ``Sum`` matches
    what the FX-aware path would produce without the FX round-trip.

    Args:
        prop: The Property instance to sum within.
        window: Either a ``date`` (interpreted as "through this date" —
            all-time) or a ``(start_date, end_date)`` tuple (the YTD
            window).
        transaction_type: ``"income"`` or ``"expense"`` — filters on the
            derived ``Transaction.type`` field.

    Returns:
        ``Decimal`` (``0`` when no rows match — the ORM ``Sum`` returns
        ``None`` for an empty queryset, which we coerce to ``0``).
    """
    from django.db.models import Sum

    qs = Transaction.objects.filter(property=prop, type=transaction_type)
    if isinstance(window, tuple):
        start_date, end_date = window
        qs = qs.filter(date__range=(start_date, end_date))
    else:
        qs = qs.filter(date__lte=window)
    return qs.aggregate(total=Sum("amount"))["total"] or 0


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
        year-to-date) denominated in ``currency`` as of ``as_of``.

        Currency handling:

        * ``currency=native`` (or omitted) — each property's aggregates
          are computed in its OWN native currency (no FX conversion). The
          sums are raw ``Transaction.amount`` totals filtered by sign.
          The frontend uses this for the Properties page and Currency
          Exposure chart, where mixing currencies via FX would obscure
          the per-property picture.
        * ``currency=USD`` (or any other code) — aggregates are
          FX-converted into that currency via
          :func:`rentals.services.financials.aggregate`.

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
                                                    # denominated in. Equals the
                                                    # request ``currency`` param
                                                    # when one is given; equals
                                                    # the property's NATIVE
                                                    # currency when ``native``
                                                    # (or no param) is given.
            }

        Expenses carry their negative sign through from the underlying
        ``Transaction.amount`` (income positive, expense negative on
        save) — ``net = income + expense`` is therefore income minus
        the absolute expense, matching what the legacy
        ``handle_element`` view rendered.
        """
        from rentals.services.financials import aggregate

        as_of = _parse_as_of(request.query_params)
        requested_currency = request.query_params.get("currency")
        # ``native`` (or omitted) => sum each property in its own currency
        # with no FX conversion. Any other value => FX-convert into that
        # currency via the financials service.
        use_native = not requested_currency or requested_currency == "native"
        year_start = date(as_of.year, 1, 1)
        year_end = date(as_of.year, 12, 31)

        properties = self.get_queryset()
        result = []
        for prop in properties:
            # The currency the aggregates will be denominated in. For the
            # native path this is the property's own currency; for the FX
            # path it's the requested target currency.
            stats_currency = prop.currency if use_native else requested_currency

            if use_native:
                # Raw face-value sums filtered to this property. The
                # ``rentals.services.financials.aggregate`` helper requires
                # a non-None target currency (it raises ValueError
                # otherwise), so for the native path we sum directly via
                # the ORM. Income = positive amounts, expense = negative.
                gross_income_all = _native_sum(prop, as_of, "income")
                expenses_all = _native_sum(prop, as_of, "expense")
                gross_income_ytd = _native_sum(prop, (year_start, year_end), "income")
                expenses_ytd = _native_sum(prop, (year_start, year_end), "expense")
            else:
                gross_income_all = aggregate(
                    Transaction,
                    end_date=as_of,
                    target_currency=stats_currency,
                    properties=[prop],
                    transaction_type="income",
                )
                expenses_all = aggregate(
                    Transaction,
                    end_date=as_of,
                    target_currency=stats_currency,
                    properties=[prop],
                    transaction_type="expense",
                )
                gross_income_ytd = aggregate(
                    Transaction,
                    end_date=year_end,
                    start_date=year_start,
                    target_currency=stats_currency,
                    properties=[prop],
                    transaction_type="income",
                )
                expenses_ytd = aggregate(
                    Transaction,
                    end_date=year_end,
                    start_date=year_start,
                    target_currency=stats_currency,
                    properties=[prop],
                    transaction_type="expense",
                )

            data = PropertySerializer(prop).data
            # Preserve the property's native ``currency`` (RUB/GBP/etc.) so
            # the frontend can group by it for the Currency Exposure chart.
            # The FX-converted currency the aggregates are denominated in
            # is exposed separately as ``stats_currency`` — previously this
            # view overwrote ``currency`` with the target currency, which
            # collapsed every property to USD in the exposure chart.
            data.update(
                {
                    "gross_income_all_time": float(gross_income_all),
                    "expenses_all_time": float(expenses_all),
                    "net_income_all_time": float(gross_income_all + expenses_all),
                    "gross_income_ytd": float(gross_income_ytd),
                    "expenses_ytd": float(expenses_ytd),
                    "net_income_ytd": float(gross_income_ytd + expenses_ytd),
                    "stats_currency": stats_currency,
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
        the request date. When ``currency=native`` (or omitted), all
        aggregates are returned in the tenant's property currency with
        no FX conversion — ``stats_currency`` then equals the property
        currency.

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
        requested_currency = request.query_params.get("currency")
        # ``native`` (or omitted) => compute in the tenant's property
        # currency without FX conversion. Any other value => FX-convert.
        use_native = not requested_currency or requested_currency == "native"
        year_start = date(as_of.year, 1, 1)
        year_end = date(as_of.year, 12, 31)

        tenants = self.get_queryset()
        result = []
        for tenant in tenants:
            # Target currency the aggregates will be denominated in. For
            # the native path it's the tenant's property currency; for
            # the FX path it's the requested currency.
            stats_currency = tenant.property.currency if use_native else requested_currency
            lease_rent = tenant.lease_rent(as_of)
            revenue_all_time = tenant.rent_total(
                as_of,
                target_currency=stats_currency,
                include_post_vacation=True,
            )
            revenue_ytd = tenant.rent_total(
                start_date=year_start,
                end_date=year_end,
                target_currency=stats_currency,
                include_post_vacation=True,
            )
            debt_value = tenant.debt(as_of)
            # ``debt`` is denominated in the tenant's property currency.
            # In the native path we pass it through unchanged; in the FX
            # path we convert into the requested currency at ``as_of``.
            if use_native:
                debt_converted = debt_value
            else:
                debt_converted = fx_service.convert(
                    debt_value,
                    tenant.property.currency,
                    stats_currency,
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
                    "stats_currency": stats_currency,
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
        # Base scope: only transactions whose ``property`` is owned by the
        # requesting user (the per-user scoping invariant every ViewSet
        # enforces).
        qs = Transaction.objects.filter(property__owned_by__user=self.request.user)
        # Honor an optional ``?property=<id>`` query param so callers can
        # narrow to one property (the property detail page does this for
        # its Recent Transactions panel). The param is scoped to the
        # user's own properties via the base filter above, so a
        # cross-landlord PK simply yields an empty list — no enumeration
        # channel.
        property_param = self.request.query_params.get("property")
        if property_param:
            qs = qs.filter(property_id=property_param)
        # Honor an optional ``?tenant=<id>`` query param so the tenant
        # detail page can narrow to that tenant's transactions (its
        # Recent Transactions panel + the per-tenant net income + YTD
        # roll-ups depend on this filter — without it the page would
        # show every transaction across the landlord's portfolio).
        # Cross-landlord PKs are scoped out by the base filter above
        # (the join through ``property__owned_by__user`` excludes rows
        # whose tenant belongs to another landlord), so this param
        # cannot be used as an enumeration channel either.
        tenant_param = self.request.query_params.get("tenant")
        if tenant_param:
            qs = qs.filter(tenant_id=tenant_param)
        # Honor an optional ``?category=<value>`` query param so callers
        # can narrow to a single transaction category (the dashboard's
        # Cash Flow drill-down links to /transactions/?category=rent and
        # expects the list to reflect it). Without this filter the
        # drill-down showed every category in the date range.
        category_param = self.request.query_params.get("category")
        if category_param:
            qs = qs.filter(category=category_param)
        # Honor the date-range filters. The frontend sends ``from`` /
        # ``to`` (mirroring the URL query params the TransactionsPage
        # reads), but we ALSO accept the DRF-idiomatic ``date__gte`` /
        # ``date__lte`` aliases so the endpoint stays friendly to API
        # clients that already speak Django lookups. The previous code
        # did not filter on either, which silently no-op'd the date
        # range in the Filter Bar.
        date_from = (
            self.request.query_params.get("from")
            or self.request.query_params.get("date__gte")
        )
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = (
            self.request.query_params.get("to")
            or self.request.query_params.get("date__lte")
        )
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

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
class FXViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to FX rows.

    FX rows are not scoped to a landlord (FX is a shared reference-table
    in this app — every landlord reads the same currency-pair rates). So
    only ``IsAuthenticated`` is applied here — there is no per-user
    ownership to enforce. Writes are intentionally unavailable from the
    web API; production FX acquisition is performed by the scheduled
    ``refresh_fx`` management command so financial requests never block on
    an external provider.
    """

    serializer_class = FXSerializer
    permission_classes = [IsAuthenticated]
    queryset = FX.objects.all()
    lookup_value_regex = r"\d+"

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
        # Base scope: only capital-structure rows whose ``property`` is
        # owned by the requesting user (the per-user scoping invariant
        # every other ViewSet in this module enforces).
        qs = Property_capital_structure.objects.filter(
            property__owned_by__user=self.request.user
        )
        # Honor an optional ``?property=<id>`` query param so callers can
        # narrow to one property (the property detail page does this for
        # its Valuations tab). The param is scoped to the user's own
        # properties via the base filter above, so a cross-landlord PK
        # simply yields an empty list — no enumeration channel.
        property_param = self.request.query_params.get("property")
        if property_param:
            qs = qs.filter(property_id=property_param)
        return qs

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


class LeaseRentViewSet(viewsets.ModelViewSet):
    """CRUD for ``Lease_rent`` scoped via ``tenant.property.owned_by.user``.

    Backs the ``/api/v1/lease-rents/`` endpoint — the write path the
    tenant detail page's "Update rent" dialog uses to push a new
    effective-date rent entry. The read path (current rent rate) is
    already served by ``TenantViewSet.with_stats``'s ``rent_rate``
    aggregate, but the spec previously deferred the write API; this
    closes that gap.

    * ``get_queryset`` — only lease-rent rows whose ``tenant.property``
      is owned by the requesting user. An optional ``?tenant=<id>``
      query param narrows further (used by future history views).
    * ``perform_create`` / ``perform_update`` — validate the
      client-supplied ``tenant`` FK belongs to the requester before save
      (404 otherwise), preventing cross-landlord rent-history injection.
      Mirrors the IDOR defense ``TenantViewSet`` /
      ``TransactionViewSet`` already use.
    """

    serializer_class = LeaseRentSerializer
    permission_classes = _OWNER_PERMS

    def get_queryset(self):
        qs = Lease_rent.objects.filter(
            tenant__property__owned_by__user=self.request.user
        )
        # Optional ``?tenant=<id>`` filter — scoped to the user's own
        # tenants via the base filter, so a cross-landlord PK yields an
        # empty list (no enumeration channel).
        tenant_param = self.request.query_params.get("tenant")
        if tenant_param:
            qs = qs.filter(tenant_id=tenant_param)
        return qs

    def _validate_and_save(self, serializer):
        """Validate ``tenant`` ownership, then save the Lease_rent.

        On PATCH (partial update) the client may omit ``tenant`` because
        it is unchanged; fall back to the existing instance. DRF's
        ``PrimaryKeyRelatedField`` resolves the FK to a model instance,
        not an id, so ``tenant_obj`` is the appropriate name.
        """
        tenant_obj = serializer.validated_data.get("tenant") or getattr(
            serializer.instance, "tenant", None
        )
        if tenant_obj is None:
            raise ValidationError({"tenant": "This field is required."})
        # Resolve via the user-scoped tenant queryset — raises 404 if
        # the tenant belongs to another landlord (defeating enumeration).
        tenant_qs = Tenant.objects.filter(
            id=tenant_obj.id, property__owned_by__user=self.request.user
        )
        if not tenant_qs.exists():
            raise ValidationError(
                {"tenant": "Tenant does not belong to a property you own."}
            )
        serializer.save()

    def perform_create(self, serializer):
        self._validate_and_save(serializer)

    def perform_update(self, serializer):
        self._validate_and_save(serializer)
