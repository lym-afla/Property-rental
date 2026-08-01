import hashlib
from collections.abc import Collection

from django.conf import settings
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import OIDCIdentity


VIEWER_GROUP = "lifeos:app:rent:viewer"
ADMIN_GROUP = "lifeos:app:rent:admin"
PROFILE_CLAIM_FIELDS = {
    "username": "preferred_username",
    "first_name": "given_name",
    "last_name": "family_name",
    "email": "email",
}


def _identity_claims(claims):
    return settings.OIDC_ISSUER, claims.get("sub")


def _clean_profile_claim(user, field_name: str, value):
    """Return a conservative, model-valid string claim value or ``None``."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    field = user._meta.get_field(field_name)
    try:
        field.clean(value, user)
    except ValidationError:
        return None
    return value


class RentalOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Bind protocol-validated claims to the provider's immutable identity."""

    def authenticate(self, request, **kwargs):
        self._authorization_groups = ()
        user = super().authenticate(request, **kwargs)
        groups = self._authorization_groups if user is not None else ()
        mark_session_authorized(request, groups)
        return user

    def verify_claims(self, claims: dict) -> bool:
        groups = claims.get(settings.OIDC_GROUPS_CLAIM)
        self._authorization_groups = (
            groups if isinstance(groups, (list, tuple, set, frozenset)) else ()
        )
        if not super().verify_claims(claims):
            return False
        issuer, subject = _identity_claims(claims)
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

    def update_user(self, user, claims: dict):
        """Project Life OS profile claims onto the local ownership record."""
        update_fields = []
        for field_name, claim_name in PROFILE_CLAIM_FIELDS.items():
            value = _clean_profile_claim(user, field_name, claims.get(claim_name))
            if value is None or getattr(user, field_name) == value:
                continue
            setattr(user, field_name, value)
            update_fields.append(field_name)

        if not settings.LOCAL_PASSWORD_AUTH_ENABLED and user.has_usable_password():
            user.set_unusable_password()
            update_fields.append("password")

        if update_fields:
            try:
                user.save(update_fields=sorted(set(update_fields)))
            except IntegrityError as exc:
                raise SuspiciousOperation("OIDC profile synchronization failed") from exc
        return user

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
        request.session.flush()
        return
    request.session["oidc_authorized_groups"] = sorted(set(groups))
    request.session["oidc_last_authorized_at"] = timezone.now().isoformat()
