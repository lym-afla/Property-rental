"""Legacy template views retired (Task 10 of Plan B2).

Every behavioral endpoint now lives behind the ``/api/v1/`` DRF namespace
in ``rentals.api`` and is consumed by the React SPA served by
``SpaView``. This module previously hosted ~1100 lines of template-view
glue (``index``, ``handle_element``, ``create_element``, ``table_data``,
``vacate_tenant``, ``property_valuation``,
``update_fx_view``, ``new_form``, ``property_choices`` plus the inline
``PropertySerializer`` / ``TenantSerializer`` / ``TransactionSerializer``
/ ``PropertyValuationSerializer`` duplicates of
``rentals.api.serializers``). All of that is gone: ``urls.py`` keeps only
the API include + the SPA catch-all, and this module keeps only
``SpaView``.

Note: the financial logic itself was already extracted into
``rentals.services.financials`` (``pnl_calc``) in earlier tasks, so
deleting the template-view shims here does NOT lose business logic. The
characterization tests import those services directly.
"""

from django.views.generic import TemplateView


# Task 6: SPA catch-all.
#
# Serves ``spa_index.html`` (the React shell rendered through django-vite)
# for any URL not claimed by the API, admin, or template-rendered routes
# wired earlier in ``rentals/urls.py``. The React Router handles client-
# side routing; we deliberately do NOT enforce auth here — protected
# pages get a 401 from the API on first fetch and the SPA redirects.
class SpaView(TemplateView):
    """Serves the built React SPA. Falls through to index.html for client-side routing."""

    template_name = 'spa_index.html'

    def get(self, request, *args, **kwargs):
        # Optionally check auth here for protected routes — but the SPA
        # handles that client-side via API 401s.
        return super().get(request, *args, **kwargs)
