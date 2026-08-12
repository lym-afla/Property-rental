from django.middleware.security import SecurityMiddleware


class InternalBackchannelSecurityMiddleware(SecurityMiddleware):
    """Permit Authentik's exact private logout callback to remain HTTP."""

    _BACKCHANNEL_PATH = "/oidc/backchannel-logout/"
    _INTERNAL_HOSTS = frozenset({"rent", "rent:8000"})

    def process_request(self, request):
        if (
            request.path_info == self._BACKCHANNEL_PATH
            and request.get_host() in self._INTERNAL_HOSTS
        ):
            return None
        return super().process_request(request)
