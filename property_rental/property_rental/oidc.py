"""Operational hooks for the OpenID Connect integration."""

from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.contrib import auth
from django.db import transaction
from django.http import HttpResponseRedirect
from mozilla_django_oidc.views import OIDCLogoutView

from rentals.models import OIDCSession


def provider_logout_url(request) -> str:
    """Return the bare provider endpoint so logout needs no stored ID token."""
    endpoint = urlsplit(settings.OIDC_LOGOUT_URL)
    return urlunsplit(endpoint._replace(query="", fragment=""))


class RentalOIDCLogoutView(OIDCLogoutView):
    """Clear Rent's complete local logout state before leaving for Authentik."""

    @transaction.atomic
    def post(self, request):
        session_key = request.session.session_key
        if session_key:
            OIDCSession.objects.filter(session_key=session_key).delete()
        auth.logout(request)
        return HttpResponseRedirect(provider_logout_url(request))
