"""URL routing for the ``rentals`` app (Task 10 of Plan B2).

All behavioral endpoints live under ``/api/v1/`` (see
``rentals.api.urls``) and are consumed by the React SPA. The legacy
template-view routes (``/handling/...``, ``/table-data/...``,
``/vacate-tenant/...``, ``/new-form/...``, ``/properties/valuation/...``,
``/get_chart_data``, ``/update-fx/``, ``/.well-known/...``) and the
top-level ``index`` route have been retired. Only two routes remain:

* ``api/v1/`` — the DRF namespace (auth + entities + analytics).
* ``''`` and non-API paths — the SPA catch-all served by ``SpaView``.

The SPA handles client-side routing; ``/api/v1/`` is registered BEFORE
the catch-all so it always wins.
"""

from django.urls import include, path, re_path

from .views import SpaView

app_name = 'rentals'

urlpatterns = [
    # DRF /api/v1/ namespace (auth + entities + analytics).
    path('api/v1/', include('rentals.api.urls')),
]

# SPA catch-all (MUST be appended LAST and exclude ``api/`` so retired or
# misspelled API routes return Django's 404 instead of the SPA shell).
urlpatterns += [
    path('', SpaView.as_view()),
    re_path(r'^(?!api/).+$', SpaView.as_view()),
]
