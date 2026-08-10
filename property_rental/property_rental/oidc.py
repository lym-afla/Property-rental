"""Operational hooks for the OpenID Connect integration."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings


def provider_logout_url(request) -> str:
    """Return the configured provider end-session endpoint with its fixed return URL."""
    endpoint = urlsplit(settings.OIDC_LOGOUT_URL)
    query = [
        (name, value)
        for name, value in parse_qsl(endpoint.query, keep_blank_values=True)
        if name != "post_logout_redirect_uri"
    ]
    query.append(
        ("post_logout_redirect_uri", settings.OIDC_POST_LOGOUT_REDIRECT_URL)
    )
    return urlunsplit(endpoint._replace(query=urlencode(query)))
