from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from django.contrib import admin
from django.http import Http404, JsonResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import include, path
from django.utils import timezone

from rentals.models import OIDCIdentity, OIDCSession, User
from rentals.oidc import ADMIN_GROUP, VIEWER_GROUP, mark_session_authorized
from rentals.api.auth import LoginView
from property_rental.oidc import RentalOIDCLogoutView
from rest_framework.test import APIRequestFactory


mutations = []


def protected_view(request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        mutations.append(request.method)
    return JsonResponse({"ok": True})


def health_view(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("protected/", protected_view),
    path("health/", health_view),
    path("oidc/logout/", RentalOIDCLogoutView.as_view(), name="oidc_logout"),
    path("oidc/", include("mozilla_django_oidc.urls")),
]


AUTH_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "rentals.middleware.AuthorizationAgeMiddleware",
]

REFRESH_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "rentals.middleware.AuthorizationAgeMiddleware",
    "mozilla_django_oidc.middleware.SessionRefresh",
]


def authorize(client, user, *, age_seconds=0, groups=(VIEWER_GROUP,)):
    client.force_login(user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")
    session = client.session
    session["oidc_authorized_groups"] = list(groups)
    session["oidc_last_authorized_at"] = (
        timezone.now() - timedelta(seconds=age_seconds)
    ).isoformat()
    session.save()


@pytest.fixture(autouse=True)
def clear_mutations(settings):
    mutations.clear()
    settings.LOCAL_PASSWORD_AUTH_ENABLED = False
    settings.AUTHENTICATION_BACKENDS = [
        "rentals.oidc.RentalOIDCAuthenticationBackend"
    ]
    settings.OIDC_OP_TOKEN_ENDPOINT = "https://auth.example/token/"
    settings.OIDC_OP_AUTHORIZATION_ENDPOINT = "https://auth.example/authorize/"
    settings.OIDC_OP_USER_ENDPOINT = "https://auth.example/userinfo/"
    settings.OIDC_OP_JWKS_ENDPOINT = "https://auth.example/jwks/"
    settings.OIDC_RP_CLIENT_ID = "rent"
    settings.OIDC_RP_CLIENT_SECRET = "secret"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=AUTH_MIDDLEWARE)
def test_fresh_authorization_reaches_protected_view():
    user = User.objects.create_user("fresh")
    client = Client()
    authorize(client, user, age_seconds=299)

    assert client.post("/protected/").status_code == 200
    assert mutations == ["POST"]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "patch", "delete"])
@override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=AUTH_MIDDLEWARE)
def test_expired_unsafe_request_is_denied_without_invoking_view(method):
    user = User.objects.create_user(f"stale-{method}")
    client = Client()
    authorize(client, user, age_seconds=300)

    response = getattr(client, method)("/protected/")

    assert response.status_code == 403
    assert response.json() == {
        "code": "authorization_refresh_required",
        "refresh_url": "/oidc/authenticate/?next=%2Fprotected%2F",
        "retry": False,
    }
    assert mutations == []


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=AUTH_MIDDLEWARE,
    OIDC_CALLBACK_URL="https://rent.example/identity/callback/",
)
def test_unsafe_refresh_url_uses_configured_oidc_route_prefix():
    user = User.objects.create_user("custom-callback")
    client = Client()
    authorize(client, user, age_seconds=300)

    response = client.post("/protected/")

    assert response.status_code == 403
    assert response.json()["refresh_url"] == (
        "/identity/authenticate/?next=%2Fprotected%2F"
    )


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=REFRESH_MIDDLEWARE,
    OIDC_OP_AUTHORIZATION_ENDPOINT="https://auth.example/authorize/",
    OIDC_RP_CLIENT_ID="rent",
)
def test_expired_xhr_get_uses_session_refresh_response():
    user = User.objects.create_user("stale-get")
    client = Client()
    authorize(client, user, age_seconds=300)

    response = client.get(
        "/protected/?next=https://evil.example/steal",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 403
    assert response.json().keys() == {"refresh_url"}
    refresh_url = response.json()["refresh_url"]
    assert refresh_url.startswith("https://auth.example/authorize/?")
    assert parse_qs(urlparse(refresh_url).query)["prompt"] == ["none"]
    assert client.session["oidc_login_next"].startswith("/protected/")


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=AUTH_MIDDLEWARE)
def test_missing_viewer_group_clears_session_and_denies_access():
    user = User.objects.create_user("revoked")
    client = Client()
    authorize(client, user, groups=(ADMIN_GROUP,))

    response = client.get("/protected/")

    assert response.status_code == 403
    assert not client.session.items()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF=__name__, MIDDLEWARE=AUTH_MIDDLEWARE)
@pytest.mark.parametrize(
    "path", ["/health/", "/oidc/authenticate/", "/oidc/callback/", "/static/app.js"]
)
def test_explicit_public_routes_are_exempt(path):
    response = Client().get(path)
    assert response.status_code != 403


def test_successful_renewal_updates_authorization_timestamp(rf):
    request = rf.get("/oidc/callback/")
    from django.contrib.sessions.middleware import SessionMiddleware

    SessionMiddleware(lambda req: None).process_request(request)
    before = timezone.now()
    mark_session_authorized(request, [VIEWER_GROUP])

    assert datetime.fromisoformat(request.session["oidc_last_authorized_at"]) >= before


@pytest.mark.django_db
def test_admin_denies_local_staff_without_admin_authorization():
    user = User.objects.create_user("staff", is_staff=True)
    request = RequestFactory().get("/admin/")
    request.user = user
    request.session = {"oidc_authorized_groups": [VIEWER_GROUP]}

    assert admin.site.has_permission(request) is False


@pytest.mark.django_db
@override_settings(LOCAL_PASSWORD_AUTH_ENABLED=False)
def test_production_user_admin_locks_life_os_identity_and_password_fields(rf):
    managed = User.objects.create_user(
        "managed",
        email="managed@example.com",
        first_name="Managed",
        last_name="Identity",
    )
    operator = User.objects.create_user(
        "operator", is_staff=True, is_superuser=True
    )
    request = rf.get(f"/admin/rentals/user/{managed.pk}/change/")
    request.user = operator
    request.session = {
        "oidc_authorized_groups": [VIEWER_GROUP, ADMIN_GROUP],
    }

    user_admin = admin.site._registry[User]

    assert {
        "username",
        "first_name",
        "last_name",
        "email",
        "password",
    }.issubset(set(user_admin.get_readonly_fields(request, managed)))


def test_development_keeps_local_password_auth_enabled():
    settings.LOCAL_PASSWORD_AUTH_ENABLED = True
    assert settings.LOCAL_PASSWORD_AUTH_ENABLED is True


def test_password_view_cannot_be_invoked_when_local_auth_is_disabled():
    request = APIRequestFactory().post(
        "/api/v1/auth/login/", {"username": "local", "password": "secret"}
    )
    with pytest.raises(Http404):
        LoginView.as_view()(request)


@pytest.mark.django_db
@override_settings(
    ROOT_URLCONF=__name__,
    ALLOW_LOGOUT_GET_METHOD=True,
    LOGOUT_REDIRECT_URL="https://auth.linik.ru/",
    OIDC_OP_LOGOUT_URL_METHOD="property_rental.oidc.provider_logout_url",
    OIDC_LOGOUT_URL="https://auth.example/application/o/rent/end-session/",
)
def test_oidc_logout_clears_the_local_session_then_uses_bare_provider_end_session():
    """A visible logout must not send a redirect that requires a stored ID token."""
    user = User.objects.create_user("logout-user")
    client = Client()
    authorize(client, user)
    identity = OIDCIdentity.objects.create(
        user=user,
        issuer="https://auth.example/application/o/rent/",
        subject="logout-user-subject",
    )
    current_session_key = client.session.session_key
    current = OIDCSession.objects.create(
        identity=identity,
        sid="current-provider-session",
        session_key=current_session_key,
    )
    unrelated_user = User.objects.create_user("unrelated-logout-user")
    unrelated_identity = OIDCIdentity.objects.create(
        user=unrelated_user,
        issuer="https://auth.example/application/o/rent/",
        subject="unrelated-subject",
    )
    unrelated = OIDCSession.objects.create(
        identity=unrelated_identity,
        sid="unrelated-provider-session",
        session_key="unrelated-session-key",
    )

    response = client.get("/oidc/logout/")

    assert response.status_code == 302
    assert response["Location"] == "https://auth.example/application/o/rent/end-session/"
    assert not client.session.items()
    assert not OIDCSession.objects.filter(pk=current.pk).exists()
    assert OIDCSession.objects.filter(pk=unrelated.pk).exists()

    repeated = client.get("/oidc/logout/")

    assert repeated.status_code == 302
    assert repeated["Location"] == "https://auth.example/application/o/rent/end-session/"
    assert OIDCSession.objects.filter(pk=unrelated.pk).exists()
