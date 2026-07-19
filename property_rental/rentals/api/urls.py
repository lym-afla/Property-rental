"""URL routing for the ``/api/v1/`` namespace (Task 17).

A :class:`rest_framework.routers.DefaultRouter` wires the four
:class:`ModelViewSet` classes (properties, tenants, transactions, fx) to
the standard REST verbs. The ``ChartDataView`` APIView is mounted
alongside as a flat ``chart-data/`` path (it is not a ViewSet — it
exposes a single GET endpoint).

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
* ``GET    /api/v1/chart-data/?type=&id=&freq=&start=&end=&currency=``
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth import LoginView, LogoutView, MeView
from .views import (
    ChartDataView,
    FXViewSet,
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

urlpatterns = [
    # Auth (Task 4) — session-cookie endpoints consumed by the SPA's
    # ``useAuth`` hook. Mounted flat (no router) because each is a
    # single-verb APIView, not a ViewSet.
    path("auth/login/", LoginView.as_view()),
    path("auth/logout/", LogoutView.as_view()),
    path("auth/me/", MeView.as_view()),
    path("chart-data/", ChartDataView.as_view()),
]
urlpatterns += router.urls
