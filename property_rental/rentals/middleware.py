from datetime import datetime
from urllib.parse import urlencode, urlparse

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.http import JsonResponse
from django.utils import timezone
from mozilla_django_oidc.middleware import SessionRefresh

from .oidc import VIEWER_GROUP


AUTHORIZED_GROUPS_SESSION_KEY = "oidc_authorized_groups"
LAST_AUTHORIZED_AT_SESSION_KEY = "oidc_last_authorized_at"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
HEALTH_CHECK_PATHS = frozenset({"/health/live", "/health/ready"})


class HealthCheckSessionRefresh(SessionRefresh):
    """Skip OIDC session inspection for process and dependency probes."""

    def is_refreshable_url(self, request):
        # Check this before SessionRefresh reads request.user, which can load
        # an authenticated session's user record from the database.
        if request.path in HEALTH_CHECK_PATHS:
            return False
        return super().is_refreshable_url(request)


class AuthorizationAgeMiddleware:
    """Fail closed when an OIDC authorization grant is missing or stale."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path) or not request.user.is_authenticated:
            return self.get_response(request)

        backend = request.session.get(BACKEND_SESSION_KEY, "")
        is_oidc_session = (
            backend == "rentals.oidc.RentalOIDCAuthenticationBackend"
            or LAST_AUTHORIZED_AT_SESSION_KEY in request.session
            or AUTHORIZED_GROUPS_SESSION_KEY in request.session
        )
        if settings.LOCAL_PASSWORD_AUTH_ENABLED and not is_oidc_session:
            return self.get_response(request)

        groups = request.session.get(AUTHORIZED_GROUPS_SESSION_KEY, ())
        if VIEWER_GROUP not in groups:
            request.session.flush()
            return JsonResponse({"code": "authorization_required"}, status=403)

        if not self._authorization_is_fresh(request):
            if request.method in SAFE_METHODS:
                # SessionRefresh remains responsible for its established GET/XHR
                # redirect and 403 refresh_url contract.
                request.session["oidc_id_token_expiration"] = 0
                return self.get_response(request)
            next_path = request.get_full_path()
            _, authenticate_path = self._oidc_routes()
            refresh_url = authenticate_path + "?" + urlencode({"next": next_path})
            return JsonResponse(
                {
                    "code": "authorization_refresh_required",
                    "refresh_url": refresh_url,
                    "retry": False,
                },
                status=403,
            )

        return self.get_response(request)

    @staticmethod
    def _oidc_routes():
        callback_path = urlparse(
            getattr(settings, "OIDC_CALLBACK_URL", "/oidc/callback/")
        ).path
        authenticate_path = callback_path[: -len("callback/")] + "authenticate/"
        return callback_path, authenticate_path

    @classmethod
    def _is_exempt(cls, path):
        callback_path, authenticate_path = cls._oidc_routes()
        return (
            path in HEALTH_CHECK_PATHS
            or path == authenticate_path
            or path == callback_path
            or path.startswith(settings.STATIC_URL)
        )

    @staticmethod
    def _authorization_is_fresh(request):
        value = request.session.get(LAST_AUTHORIZED_AT_SESSION_KEY)
        try:
            authorized_at = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return False
        if timezone.is_naive(authorized_at):
            return False
        age = (timezone.now() - authorized_at).total_seconds()
        return 0 <= age < settings.OIDC_AUTHORIZATION_MAX_AGE
