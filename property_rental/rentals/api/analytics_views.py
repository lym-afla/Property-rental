"""Authenticated HTTP endpoints for portfolio analytics responses."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rentals.analytics.cash_flow import expense_drivers, portfolio_cash_flow
from rentals.analytics.filters import AnalyticsFilters
from rentals.api.analytics_serializers import TimeSeriesResponseSerializer
from rentals.utils import get_effective_date


class _PortfolioAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def filters(self, request):
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
