"""Operational hooks for the OpenID Connect integration."""

from django.conf import settings


def provider_logout_url(request) -> str:
    """Return the configured provider end-session endpoint."""
    return settings.OIDC_LOGOUT_URL
