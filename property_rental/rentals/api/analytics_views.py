"""Authenticated HTTP endpoints for portfolio analytics responses."""

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rentals.analytics.cash_flow import expense_drivers, portfolio_cash_flow
from rentals.analytics.filters import AnalyticsFilters, ISODateField
from rentals.analytics.portfolio import (
    currency_exposure,
    portfolio_occupancy,
    portfolio_summary,
    property_contribution,
    property_yields,
)
from rentals.analytics.property import property_valuation_history
from rentals.analytics.tenant import tenant_rent_performance
from rentals.constants import CURRENCY_CHOICES
from rentals.api.analytics_serializers import (
    ContributionResponseSerializer,
    CurrencyExposureResponseSerializer,
    PortfolioSummarySerializer,
    PropertyValuationResponseSerializer,
    TenantRentPerformanceResponseSerializer,
    TimeSeriesResponseSerializer,
    YieldResponseSerializer,
)
from rentals.utils import get_effective_date


class _ValuationEndSerializer(serializers.Serializer):
    end = ISODateField(required=False)


class _PortfolioAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

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


class PortfolioCurrencyExposureView(_PortfolioAnalyticsView):
    def get(self, request):
        measure = request.query_params.get("measure", "property_value")
        if measure not in {"property_value", "debt", "rental_income"}:
            raise serializers.ValidationError({"measure": "Unsupported measure."})
        result = currency_exposure(
            request.user,
            self.filters(request, extra_query_params=("measure",)),
            measure=measure,
        )
        return Response(CurrencyExposureResponseSerializer(result).data)


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
        allowed = {"start", "end", "grain", "currency"}
        unknown = set(request.query_params) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "Unknown filter." for key in sorted(unknown)}
            )
        result = tenant_rent_performance(
            request.user, tenant_id, self.filters(request)
        )
        return Response(TenantRentPerformanceResponseSerializer(result).data)
