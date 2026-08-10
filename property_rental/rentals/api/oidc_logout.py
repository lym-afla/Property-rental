"""Server-to-server endpoint for signed OIDC back-channel logout."""

import jwt
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters

from rentals.oidc_logout import invalidate_oidc_sessions, validate_logout_token


def _empty_response(status: int) -> HttpResponse:
    response = HttpResponse(status=status)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(sensitive_post_parameters("logout_token"), name="dispatch")
class BackChannelLogoutView(View):
    http_method_names = ["post"]

    def post(self, request):
        if request.content_type not in (
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ):
            return _empty_response(400)
        raw_token = request.POST.get("logout_token")
        if not raw_token:
            return _empty_response(400)

        try:
            claims = validate_logout_token(raw_token)
            invalidate_oidc_sessions(claims)
        except jwt.PyJWTError:
            return _empty_response(400)
        return _empty_response(200)
