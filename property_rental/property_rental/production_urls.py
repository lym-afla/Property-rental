"""Production URL configuration, including the configured OIDC callback route."""

from urllib.parse import urlparse

from django.conf import settings
from django.urls import include, path

from rentals.api.oidc_logout import BackChannelLogoutView

from .urls import handler404, urlpatterns as base_urlpatterns


_callback_path = urlparse(settings.OIDC_CALLBACK_URL).path.lstrip("/")
if not _callback_path.endswith("callback/"):
    raise RuntimeError("OIDC_CALLBACK_URL must end with /callback/")

_oidc_prefix = _callback_path[: -len("callback/")]

urlpatterns = [
    path(
        "oidc/backchannel-logout/",
        BackChannelLogoutView.as_view(),
        name="oidc_backchannel_logout",
    ),
    path(_oidc_prefix, include("mozilla_django_oidc.urls")),
    *[
        pattern for pattern in base_urlpatterns
        if getattr(pattern.pattern, "_route", "") != "oidc/"
    ],
]
