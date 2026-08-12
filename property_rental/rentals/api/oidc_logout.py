"""Server-to-server endpoint for signed OIDC back-channel logout."""

import json
import logging

import jwt
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters

from rentals.oidc_logout import invalidate_oidc_sessions, validate_logout_token


LOGGER = logging.getLogger(__name__)


def _rejection_reason(error: jwt.PyJWTError) -> str:
    if isinstance(error, jwt.PyJWKClientConnectionError):
        return "jwks_fetch"
    if isinstance(error, jwt.InvalidIssuerError):
        return "issuer"
    if isinstance(error, jwt.InvalidAudienceError):
        return "audience"
    if isinstance(error, (jwt.InvalidSignatureError, jwt.DecodeError)):
        return "decode_signature"
    if isinstance(error, jwt.ExpiredSignatureError):
        return "expired"

    message = str(error)
    if message == "nonce is not permitted in a logout token":
        return "nonce"
    if message == "invalid logout event":
        return "events"
    if message == "missing logout target":
        return "sid_sub"
    if message in {
        "invalid iat claim",
        "logout token issued in the future",
        "logout token is stale",
    }:
        return "iat"
    return "registered_claim"


def _reject(reason_code: str) -> HttpResponse:
    LOGGER.warning(json.dumps({
        "event": "oidc_backchannel_logout_rejected",
        "reason_code": reason_code,
    }, separators=(",", ":"), sort_keys=True))
    return _empty_response(400)


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
            return _reject("missing_form")
        raw_token = request.POST.get("logout_token")
        if not raw_token:
            return _reject("missing_form")

        try:
            claims = validate_logout_token(raw_token)
            invalidate_oidc_sessions(claims)
        except jwt.PyJWTError as error:
            return _reject(_rejection_reason(error))
        return _empty_response(200)
