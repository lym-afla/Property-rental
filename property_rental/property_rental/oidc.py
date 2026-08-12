"""Operational hooks for the OpenID Connect integration."""

from urllib.parse import urlsplit, urlunsplit

from django.conf import settings


def provider_logout_url(request) -> str:
    """Return the bare provider endpoint so logout needs no stored ID token."""
    endpoint = urlsplit(settings.OIDC_LOGOUT_URL)
    return urlunsplit(endpoint._replace(query="", fragment=""))
