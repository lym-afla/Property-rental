"""Authenticated HTTP endpoints for portfolio analytics responses."""

from dataclasses import dataclass
from datetime import date

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rentals.analytics.cash_flow import expense_drivers, portfolio_cash_flow
from rentals.analytics.filters import (
    MAX_ANALYTICS_POINTS,
    AnalyticsFilters,
    Grain,
    ISODateField,
)
from rentals.analytics.pnl import profit_and_loss
from rentals.analytics.portfolio import (
    portfolio_occupancy,
    portfolio_summary,
    property_breakdown,
    property_contribution,
    property_yields,
)
from rentals.analytics.property import property_valuation_history
from rentals.analytics.tenant import MissingTenantCurrency, tenant_rent_performance
from rentals.constants import CURRENCY_CHOICES
from rentals.api.analytics_serializers import (
    ContributionResponseSerializer,
    PropertyBreakdownResponseSerializer,
    PortfolioSummarySerializer,
    ProfitLossResponseSerializer,
    PropertyValuationResponseSerializer,
    TenantRentPerformanceResponseSerializer,
    TimeSeriesResponseSerializer,
    YieldResponseSerializer,
)
from rentals.utils import get_effective_date
from rentals.services.fx import MissingFXRate


class _ValuationEndSerializer(serializers.Serializer):
    end = ISODateField(required=False)


@dataclass(frozen=True)
class _TenantRentPerformanceFilters:
    start: date
    end: date
    grain: Grain


class _TenantRentPerformanceFilterSerializer(serializers.Serializer):
    start = ISODateField(required=False)
    end = ISODateField(required=False)
    grain = serializers.ChoiceField(
        choices=[grain.value for grain in Grain], required=False
    )

    def validate(self, values):
        end = values.get("end", self.context["effective_date"])
        start = values.get("start", end.replace(month=1, day=1))
        if end < start:
            raise serializers.ValidationError(
                {"end": "end must be on or after start"}
            )

        grain = Grain(values.get("grain", Grain.MONTH.value))
        start_month = start.year * 12 + start.month - 1
        end_month = end.year * 12 + end.month - 1
        if grain is Grain.MONTH:
            point_count = end_month - start_month + 1
        elif grain is Grain.QUARTER:
            point_count = end_month // 3 - start_month // 3 + 1
        else:
            point_count = end.year - start.year + 1
        if point_count > MAX_ANALYTICS_POINTS:
            raise serializers.ValidationError(
                {
                    "start": (
                        "Analytics ranges may contain at most "
                        f"{MAX_ANALYTICS_POINTS} {grain.value} buckets."
                    )
                }
            )

        return {"start": start, "end": end, "grain": grain}


class _PortfolioAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, MissingFXRate):
            return Response(
                {"code": "missing_fx", "detail": str(exc)},
                status=422,
            )
        return super().handle_exception(exc)

    def filters(self, request, extra_query_params=()):
        allowed = {
            "start",
            "end",
            "grain",
            "currency",
            "comparison",
            "property",
            *extra_query_params,
        }
        unknown = set(request.query_params) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown filter." for key in sorted(unknown)}
            )
        if "comparison" in request.query_params:
            raise serializers.ValidationError(
                {"comparison": "Comparison is not supported by this endpoint."}
            )
        if "currency" in request.query_params:
            supported_currencies = {code for code, _label in CURRENCY_CHOICES}
            if request.query_params["currency"].upper() not in supported_currencies:
                raise serializers.ValidationError(
                    {"currency": "Unsupported reporting currency."}
                )
        return AnalyticsFilters.from_query_params(
            request.query_params,
            default_currency=request.user.default_currency,
            effective_date=get_effective_date(request.user),
        )

    def response(self, analytics_response):
        return Response(TimeSeriesResponseSerializer(analytics_response).data)


class PortfolioCashFlowView(_PortfolioAnalyticsView):
    """GET the signed portfolio cash-flow trend for the authenticated user."""

    def get(self, request):
        return self.response(portfolio_cash_flow(request.user, self.filters(request)))


class PortfolioExpenseDriversView(_PortfolioAnalyticsView):
    """GET expense-category trends for the authenticated user's portfolio."""

    def get(self, request):
        return self.response(expense_drivers(request.user, self.filters(request)))


class PortfolioProfitLossView(_PortfolioAnalyticsView):
    """GET the shared annual and YTD portfolio/property P&L statement."""

    def get(self, request):
        unknown = set(request.query_params) - {"end", "currency", "property"}
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown filter." for key in sorted(unknown)}
            )
        filters = self.filters(request)
        result = profit_and_loss(
            request.user,
            end=filters.end,
            currency=filters.currency,
            property_ids=filters.property_ids,
        )
        return Response(ProfitLossResponseSerializer(result).data)


class PortfolioSummaryView(_PortfolioAnalyticsView):
    def get(self, request):
        result = portfolio_summary(request.user, self.filters(request))
        return Response(PortfolioSummarySerializer(result).data)


class PortfolioContributionView(_PortfolioAnalyticsView):
    def get(self, request):
        result = property_contribution(request.user, self.filters(request))
        return Response(ContributionResponseSerializer(result).data)


class PortfolioYieldsView(_PortfolioAnalyticsView):
    def get(self, request):
        result = property_yields(request.user, self.filters(request))
        return Response(YieldResponseSerializer(result).data)


class PortfolioPropertyBreakdownView(_PortfolioAnalyticsView):
    def get(self, request):
        measure = request.query_params.get("measure", "property_value")
        if measure not in {"property_value", "equity", "debt", "rental_income"}:
            raise serializers.ValidationError({"measure": "Unsupported measure."})
        result = property_breakdown(
            request.user,
            self.filters(request, extra_query_params=("measure",)),
            measure=measure,
        )
        return Response(PropertyBreakdownResponseSerializer(result).data)


class PortfolioOccupancyView(_PortfolioAnalyticsView):
    def get(self, request):
        result = portfolio_occupancy(request.user, self.filters(request))
        return self.response(result)


class PropertyValuationAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, property_id):
        unknown = set(request.query_params) - {"end"}
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown filter." for key in sorted(unknown)}
            )
        query = _ValuationEndSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        end = query.validated_data.get("end", get_effective_date(request.user))
        result = property_valuation_history(request.user, property_id, end=end)
        return Response(PropertyValuationResponseSerializer(result).data)


class TenantRentPerformanceAnalyticsView(_PortfolioAnalyticsView):
    def get(self, request, tenant_id):
        allowed = {"start", "end", "grain"}
        unknown = set(request.query_params) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown filter." for key in sorted(unknown)}
            )
        query = _TenantRentPerformanceFilterSerializer(
            data=request.query_params,
            context={"effective_date": get_effective_date(request.user)},
        )
        query.is_valid(raise_exception=True)
        filters = _TenantRentPerformanceFilters(**query.validated_data)
        try:
            result = tenant_rent_performance(
                request.user, tenant_id, filters
            )
        except MissingTenantCurrency as exc:
            return Response(
                {"code": "missing_currency", "detail": str(exc)},
                status=422,
            )
        return Response(TenantRentPerformanceResponseSerializer(result).data)
