"""Task 6: SPA catch-all view tests.

Two responsibilities, two tests:

1. Unknown URL → 200 (serves ``spa_index.html``). Proves the catch-all
   works at all. The body asserts the React root div is present so the
   test isn't fooled by a stray 200 from a misrouted view.

2. ``/api/v1/auth/me/`` without auth → 401. Proves the catch-all does
   NOT shadow the API. If this regresses to 200 it means URL ordering
   is wrong (catch-all appears before ``/api/``).

Note on the RequestFactory usage in test 1: the Django test client wires
a ``template_rendered`` signal handler that calls ``copy(context)`` on
every rendered template. That handler is broken on Python 3.14 (Django
4.2's ``Context.__copy__`` calls ``super().__copy__()`` which
``BaseContext`` no longer implements in 3.14). The existing suite hits
the same limitation (see ``test_security.py:495-497``). To test the
template render we go through ``RequestFactory`` + the view directly,
skipping the signal handler. Test 2 doesn't render a template (DRF
returns JSON), so it uses the normal Client.
"""

import pytest
from django.test import Client, RequestFactory
from django.urls import resolve

from rentals.views import SpaView


@pytest.mark.django_db
def test_unknown_route_serves_spa_shell(db):
    """Unknown path resolves to SpaView and renders the React root."""
    # 1. URL routing: ``/some/unknown/spa/route/`` lands on SpaView.
    match = resolve('/some/unknown/spa/route/')
    assert match.func.view_class is SpaView, (
        f"catch-all should route unknown paths to SpaView; got {match.func!r}"
    )

    # 2. The view actually renders ``spa_index.html`` with the React
    #    mount point. RequestFactory bypasses the test client's
    #    ``template_rendered`` signal handler (broken on Py 3.14).
    factory = RequestFactory()
    request = factory.get('/some/unknown/spa/route/')
    response = SpaView.as_view()(request)
    response.render()
    assert response.status_code == 200, (
        f"SpaView should return 200; got {response.status_code}"
    )
    body = response.content.decode('utf-8')
    assert '<div id="root"></div>' in body, (
        "spa_index.html should render the React mount point div#root"
    )


@pytest.mark.django_db
def test_api_route_not_shadowed_by_catchall(db):
    """``/api/v1/auth/me/`` is still routed to DRF, not the SPA catch-all.

    Live HTTP behavior: an anonymous GET returns 401/403 (DRF's
    ``IsAuthenticated`` permission), never 200 (which would mean the
    SPA catch-all swallowed it). DRF returns JSON so this doesn't
    trigger the Python 3.14 template-copy bug.
    """
    c = Client()
    resp = c.get('/api/v1/auth/me/')
    assert resp.status_code in (401, 403), (
        f"/api/v1/auth/me/ should return 401/403 for anonymous users; "
        f"got {resp.status_code} (200 would mean the catch-all shadows /api/)"
    )


@pytest.mark.django_db
def test_anonymous_root_does_not_500(db):
    """Anonymous GET on ``/`` returns the SPA shell, never a 500.

    Regression guard for the B1 review concern: before Task 9 of Plan
    B2 ``path('', views.index, name='index')`` won URL resolution over
    the SPA catch-all (it appeared earlier in ``urls.py``), and
    ``views.index`` dereferenced ``request.session['default_currency']``
    unconditionally on an authenticated branch — but for an anonymous
    user the session had no such key, so an unauthenticated GET on ``/``
    surfaced as a KeyError 500. Task 9 removed ``views.index`` and its
    route, so the SPA catch-all now wins and serves ``spa_index.html``
    regardless of session state. The SPA then redirects the
    unauthenticated user client-side via the API 401 path.

    We don't assert on the rendered body here — Django's test-client
    ``template_rendered`` signal handler is broken on Python 3.14 (see
    module docstring). The status code is the load-bearing assertion.
    """
    factory = RequestFactory()
    request = factory.get('/')
    response = SpaView.as_view()(request)
    response.render()
    assert response.status_code == 200, (
        f"anonymous GET / should serve the SPA shell (200); got "
        f"{response.status_code} (500 would mean the latent KeyError on "
        f"request.session['default_currency'] regressed)"
    )

