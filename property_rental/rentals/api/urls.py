"""URL routing for the ``/api/v1/`` namespace (Task 17).

A :class:`rest_framework.routers.DefaultRouter` wires the four
:class:`ModelViewSet` classes (properties, tenants, transactions, fx) to
the standard REST verbs.

Mounted under ``api/v1/`` from ``rentals/urls.py``:

* ``GET    /api/v1/properties/``           — list
* ``POST   /api/v1/properties/``           — create
* ``GET    /api/v1/properties/<id>/``      — retrieve
* ``PUT    /api/v1/properties/<id>/``      — update
* ``PATCH  /api/v1/properties/<id>/``      — partial update
* ``DELETE /api/v1/properties/<id>/``      — destroy
* ``/api/v1/tenants/...``                  — same shape
* ``/api/v1/transactions/...``             — same shape
* ``/api/v1/fx/...``                       — same shape
* ``/api/v1/property-valuations/...``      — same shape (Task 5; retires
  ``handle_element``'s ``data_type='propertyValuation'`` branch)
* ``/api/v1/lease-rents/...``              — same shape; backs the tenant
  detail page's "Update rent" dialog (POST creates a new effective-date
  rent entry on the tenant's ``Lease_rent`` history).
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth import (
    ChangePasswordView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)
from .analytics_views import (
    PortfolioCashFlowView,
    PortfolioContributionView,
    PortfolioCurrencyExposureView,
    PortfolioExpenseDriversView,
    PortfolioOccupancyView,
    PortfolioSummaryView,
    PortfolioYieldsView,
    PropertyValuationAnalyticsView,
    TenantRentPerformanceAnalyticsView,
)
from .views import (
    FXViewSet,
    LeaseRentViewSet,
    PropertyCapitalStructureViewSet,
    PropertyViewSet,
    TenantViewSet,
    TransactionViewSet,
)

router = DefaultRouter()
# ``basename`` is required because the ViewSets override ``get_queryset``
# instead of setting a class-level ``queryset`` attribute (the router
# otherwise can't auto-derive a basename). Basenames are used for reverse
# URL resolution; the URL prefix is set by the first arg.
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"tenants", TenantViewSet, basename="tenant")
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"fx", FXViewSet, basename="fx")
router.register(r"property-valuations", PropertyCapitalStructureViewSet, basename="property-valuation")
router.register(r"lease-rents", LeaseRentViewSet, basename="lease-rent")

urlpatterns = [
    # Auth (Task 4 / Task 5) — session-cookie endpoints consumed by the
    # SPA's ``useAuth`` hook. Mounted flat (no router) because each is a
    # single-verb APIView, not a ViewSet.
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    # Task 8: change the current user's password. Wraps Django's
    # PasswordChangeForm; body ``{old_password, new_password1,
    # new_password2}`` → 200 on success or 400 with form errors.
    path("auth/change-password/", ChangePasswordView.as_view()),
    path("auth/register/", RegisterView.as_view()),
    # Task 13: stamps the ``csrftoken`` cookie on a GET so the SPA can
    # issue authenticated mutations (logout, etc.). The SPA's
    # SessionProvider hits this once on app boot.
    path("auth/csrf/", CsrfView.as_view()),
    path("analytics/portfolio/cash-flow/", PortfolioCashFlowView.as_view()),
    path("analytics/portfolio/expenses/", PortfolioExpenseDriversView.as_view()),
    path("analytics/portfolio/summary/", PortfolioSummaryView.as_view()),
    path(
        "analytics/portfolio/property-contribution/",
        PortfolioContributionView.as_view(),
    ),
    path("analytics/portfolio/yields/", PortfolioYieldsView.as_view()),
    path(
        "analytics/portfolio/currency-exposure/",
        PortfolioCurrencyExposureView.as_view(),
    ),
    path("analytics/portfolio/occupancy/", PortfolioOccupancyView.as_view()),
    path(
        "analytics/properties/<int:property_id>/valuation/",
        PropertyValuationAnalyticsView.as_view(),
    ),
    path(
        "analytics/tenants/<int:tenant_id>/rent-performance/",
        TenantRentPerformanceAnalyticsView.as_view(),
    ),
]
urlpatterns += router.urls
