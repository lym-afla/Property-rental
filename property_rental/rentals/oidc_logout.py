"""Validation and session invalidation for OIDC back-channel logout."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from functools import lru_cache

import jwt
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import OIDCLogoutReplay, OIDCSession


BACKCHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"
REPLAY_PRUNE_LIMIT = 100


@dataclass(frozen=True)
class LogoutClaims:
    issuer: str
    subject: str | None
    sid: str | None
    jti: str
    issued_at: datetime


def _nonempty_identifier(
    claims: dict, name: str, *, max_length: int
) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, str)
        or not value
        or len(value) > max_length
    ):
        raise jwt.InvalidTokenError(f"invalid {name} claim")
    return value


@lru_cache(maxsize=8)
def _get_jwk_client(endpoint: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(endpoint, lifespan=300, timeout=5)


def validate_logout_token(raw_token: str, now: datetime | None = None) -> LogoutClaims:
    """Verify a signed OIDC logout token and return its logout-safe claims."""
    if not isinstance(raw_token, str) or not raw_token:
        raise jwt.InvalidTokenError("missing logout token")

    signing_key = _get_jwk_client(
        settings.OIDC_OP_JWKS_ENDPOINT
    ).get_signing_key_from_jwt(raw_token)
    claims = jwt.decode(
        raw_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.OIDC_RP_CLIENT_ID,
        issuer=settings.OIDC_ISSUER,
        options={
            "require": ["iss", "aud", "iat", "jti", "events"],
            "verify_iat": False,
        },
    )

    issuer = _nonempty_identifier(claims, "iss", max_length=500)
    jti = _nonempty_identifier(claims, "jti", max_length=255)
    sid = _nonempty_identifier(claims, "sid", max_length=255)
    subject = _nonempty_identifier(claims, "sub", max_length=255)
    if sid is None and subject is None:
        raise jwt.InvalidTokenError("missing logout target")
    if claims.get("events") != {BACKCHANNEL_LOGOUT_EVENT: {}}:
        raise jwt.InvalidTokenError("invalid logout event")

    iat = claims["iat"]
    if isinstance(iat, bool) or not isinstance(iat, (int, float)):
        raise jwt.InvalidTokenError("invalid iat claim")
    try:
        issued_at = datetime.fromtimestamp(iat, tz=datetime_timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise jwt.InvalidTokenError("invalid iat claim") from error
    current_time = now or timezone.now()
    if timezone.is_naive(current_time):
        current_time = timezone.make_aware(current_time, datetime_timezone.utc)
    max_age = settings.OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS
    if issued_at > current_time + timedelta(seconds=60):
        raise jwt.InvalidTokenError("logout token issued in the future")
    if current_time - issued_at > timedelta(seconds=max_age):
        raise jwt.InvalidTokenError("logout token is stale")

    return LogoutClaims(
        issuer=issuer,
        subject=subject,
        sid=sid,
        jti=jti,
        issued_at=issued_at,
    )


def invalidate_oidc_sessions(claims: LogoutClaims) -> int:
    """Record a logout notification once and delete its Django sessions."""
    max_age = settings.OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS
    expires_at = claims.issued_at + timedelta(seconds=max_age)

    with transaction.atomic():
        try:
            with transaction.atomic():
                OIDCLogoutReplay.objects.create(
                    issuer=claims.issuer,
                    jti=claims.jti,
                    expires_at=expires_at,
                )
        except IntegrityError:
            return 0

        sessions = OIDCSession.objects.filter(identity__issuer=claims.issuer)
        if claims.sid is not None:
            sessions = sessions.filter(sid=claims.sid)
        else:
            sessions = sessions.filter(identity__subject=claims.subject)

        targets = list(sessions.values_list("pk", "session_key"))
        if targets:
            Session.objects.filter(
                session_key__in=[session_key for _, session_key in targets]
            ).delete()
            OIDCSession.objects.filter(pk__in=[pk for pk, _ in targets]).delete()

        expired_replay_ids = list(
            OIDCLogoutReplay.objects.filter(expires_at__lt=timezone.now())
            .order_by("expires_at")
            .values_list("pk", flat=True)[:REPLAY_PRUNE_LIMIT]
        )
        if expired_replay_ids:
            OIDCLogoutReplay.objects.filter(pk__in=expired_replay_ids).delete()

        return len(targets)
