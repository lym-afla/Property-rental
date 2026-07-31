import hashlib
from collections.abc import Collection

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import OIDCIdentity


VIEWER_GROUP = "lifeos:app:rent:viewer"
ADMIN_GROUP = "lifeos:app:rent:admin"


def _identity_claims(claims):
    return claims.get("iss"), claims.get("sub")


class RentalOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Bind protocol-validated claims to the provider's immutable identity."""

    def verify_claims(self, claims: dict) -> bool:
        if not super().verify_claims(claims):
            return False
        issuer, subject = _identity_claims(claims)
        groups = claims.get(settings.OIDC_GROUPS_CLAIM)
        return bool(
            issuer == settings.OIDC_ISSUER
            and subject
            and isinstance(groups, (list, tuple, set, frozenset))
            and VIEWER_GROUP in groups
        )

    def filter_users_by_claims(self, claims: dict):
        issuer, subject = _identity_claims(claims)
        if not issuer or not subject:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(
            oidc_identity__issuer=issuer, oidc_identity__subject=subject
        )

    @transaction.atomic
    def create_user(self, claims: dict):
        issuer, subject = _identity_claims(claims)
        if not issuer or not subject:
            raise ValueError("OIDC claims require issuer and subject")
        digest = hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()
        user = self.UserModel(username=f"oidc_{digest[:32]}", email=claims.get("email", ""))
        user.set_unusable_password()
        user.save()
        OIDCIdentity.objects.create(user=user, issuer=issuer, subject=subject)
        return user


def mark_session_authorized(request, groups: Collection[str]) -> None:
    """Record renewed authorization without retaining provider tokens."""
    if VIEWER_GROUP not in groups:
        return
    request.session["oidc_authorized_groups"] = sorted(set(groups))
    request.session["oidc_last_authorized_at"] = timezone.now().isoformat()
