from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings
from django.contrib.sessions.middleware import SessionMiddleware

from rentals.models import OIDCIdentity, User
from rentals.oidc import RentalOIDCAuthenticationBackend, mark_session_authorized


ISSUER = "https://auth.example/application/o/rent/"
VIEWER = "lifeos:app:rent:viewer"


@pytest.fixture
def backend():
    with override_settings(
        OIDC_ISSUER=ISSUER,
        OIDC_GROUPS_CLAIM="groups",
        OIDC_RP_CLIENT_ID="rent",
        OIDC_RP_CLIENT_SECRET="secret",
        OIDC_OP_TOKEN_ENDPOINT="https://auth.example/token/",
        OIDC_OP_USER_ENDPOINT="https://auth.example/userinfo/",
        OIDC_OP_JWKS_ENDPOINT="https://auth.example/jwks/",
    ):
        yield RentalOIDCAuthenticationBackend()


@pytest.mark.django_db
def test_oidc_identity_rejects_duplicate_issuer_and_subject():
    OIDCIdentity.objects.create(user=User.objects.create_user("one"), issuer=ISSUER, subject="abc")
    with pytest.raises(IntegrityError), transaction.atomic():
        OIDCIdentity.objects.create(user=User.objects.create_user("two"), issuer=ISSUER, subject="abc")


@pytest.mark.django_db
def test_oidc_identity_rejects_second_identity_for_one_user():
    user = User.objects.create_user("one")
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")
    with pytest.raises(IntegrityError), transaction.atomic():
        OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="def")


@pytest.mark.django_db
def test_oidc_identity_issuer_and_subject_cannot_be_changed():
    identity = OIDCIdentity.objects.create(
        user=User.objects.create_user("one"), issuer=ISSUER, subject="abc"
    )
    identity.subject = "replacement"

    with pytest.raises(ValidationError):
        identity.save()


@pytest.mark.django_db
def test_binding_lookup_ignores_mutable_username_and_email(backend):
    user = User.objects.create_user("old-name", email="old@example.com")
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")
    user.username = "new-name"
    user.email = "new@example.com"
    user.save()

    assert list(backend.filter_users_by_claims({"iss": ISSUER, "sub": "abc", "email": "other@example.com"})) == [user]


def test_claims_without_viewer_group_are_denied(backend):
    with patch("mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims", return_value=True):
        assert not backend.verify_claims({"iss": ISSUER, "sub": "abc", "groups": []})


def test_claims_use_configured_issuer_and_require_userinfo_subject(backend):
    with patch("mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims", return_value=True):
        assert not backend.verify_claims({"iss": ISSUER, "groups": [VIEWER]})
        assert backend.verify_claims({"sub": "abc", "groups": [VIEWER]})


@pytest.mark.django_db
def test_created_oidc_user_has_unusable_password_and_durable_identity(backend):
    user = backend.create_user({"iss": ISSUER, "sub": "abc", "email": "person@example.com"})

    assert not user.has_usable_password()
    assert user.oidc_identity.issuer == ISSUER
    assert user.oidc_identity.subject == "abc"


@pytest.mark.django_db
def test_matching_email_does_not_merge_a_local_account(backend):
    local = User.objects.create_user("local", email="person@example.com")

    assert not backend.filter_users_by_claims({"iss": ISSUER, "sub": "new", "email": local.email}).exists()
    oidc_user = backend.create_user({"iss": ISSUER, "sub": "new", "email": local.email})
    assert oidc_user != local


def test_session_authorization_changes_only_for_viewer_claims():
    request = RequestFactory().get("/")
    SessionMiddleware(lambda req: None).process_request(request)

    mark_session_authorized(request, ["unrelated"])
    assert not request.session.items()

    mark_session_authorized(request, [VIEWER, "another"])
    assert request.session["oidc_authorized_groups"] == ["another", VIEWER]
    assert request.session["oidc_last_authorized_at"].endswith("+00:00")


def test_successful_oidc_login_records_authorized_groups_and_timestamp(backend):
    request = RequestFactory().get("/oidc/callback/")
    request.session = {}
    user = object()
    claims = {"iss": ISSUER, "sub": "abc", "email": "a@example.com", "groups": [VIEWER]}

    def protocol_authentication(request, **kwargs):
        assert backend.verify_claims(claims)
        return user

    with patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.authenticate",
        side_effect=protocol_authentication,
    ), patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims",
        return_value=True,
    ):
        assert backend.authenticate(request, code="validated-by-parent") is user

    assert request.session["oidc_authorized_groups"] == [VIEWER]
    assert request.session["oidc_last_authorized_at"].endswith("+00:00")


def test_oidc_login_without_viewer_clears_stale_session_authorization(backend):
    request = RequestFactory().get("/oidc/callback/")
    SessionMiddleware(lambda req: None).process_request(request)
    request.session["_auth_user_id"] = "42"
    request.session["oidc_authorized_groups"] = [VIEWER]
    request.session["oidc_last_authorized_at"] = "2026-01-01T00:00:00+00:00"
    claims = {"iss": ISSUER, "sub": "abc", "email": "a@example.com", "groups": []}

    def protocol_authentication(request, **kwargs):
        assert not backend.verify_claims(claims)
        return None

    with patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.authenticate",
        side_effect=protocol_authentication,
    ), patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims",
        return_value=True,
    ):
        assert backend.authenticate(request, code="validated-by-parent") is None

    assert not request.session.items()
