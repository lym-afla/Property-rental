import pytest
from django.conf import settings
from django.contrib.auth import login
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, override_settings
from unittest.mock import patch

from rentals.models import OIDCIdentity, OIDCSession, User
from rentals.oidc import (
    OIDC_SESSION_ISSUER_KEY,
    OIDC_SESSION_SID_KEY,
    OIDC_SESSION_SUBJECT_KEY,
    RentalOIDCAuthenticationBackend,
)


ISSUER = "https://auth.example/application/o/rent/"
VIEWER = "lifeos:app:rent:viewer"


def _oidc_callback_request(*, code: str):
    request = RequestFactory().get(
        "/oidc/callback/", {"code": code, "state": f"state-{code}"}
    )
    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    return request


def _authenticate_verified_oidc_callback(
    request, *, linked_user, sid, subject="person-123"
):
    payload = {
        "iss": ISSUER,
        "sub": subject,
        "sid": sid,
        "nonce": f"nonce-{subject}",
        "aud": "rent",
    }
    userinfo = {
        "sub": subject,
        "email": f"{subject}@example.com",
        "groups": [VIEWER],
    }
    backend = RentalOIDCAuthenticationBackend()
    with patch.object(
        backend,
        "get_token",
        return_value={"access_token": "opaque-access", "id_token": "signed-id"},
    ), patch.object(backend, "verify_token", return_value=payload), patch.object(
        backend, "get_userinfo", return_value=userinfo
    ), patch("mozilla_django_oidc.auth.reverse", return_value="/oidc/callback/"):
        user = backend.authenticate(request, nonce=payload["nonce"])
    assert user is None or user == linked_user
    return user


@pytest.fixture
def linked_user(db):
    user = User.objects.create_user("linked-user")
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="person-123")
    return user


@pytest.mark.django_db
@override_settings(
    OIDC_ISSUER=ISSUER,
    OIDC_GROUPS_CLAIM="groups",
    OIDC_RP_CLIENT_ID="rent",
    OIDC_RP_CLIENT_SECRET="secret",
    OIDC_OP_TOKEN_ENDPOINT="https://auth.example/token/",
    OIDC_OP_USER_ENDPOINT="https://auth.example/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://auth.example/jwks/",
    OIDC_CREATE_USER=False,
)
def test_verified_id_token_sid_survives_userinfo_and_login_session_rotation(linked_user):
    """Reading sid from userinfo instead of the verified ID token loses logout binding."""
    request = _oidc_callback_request(code="one")

    user = _authenticate_verified_oidc_callback(
        request, linked_user=linked_user, sid="provider-session-123"
    )
    assert user == linked_user

    pre_login_session_key = request.session.session_key
    login(request, user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")

    registered = OIDCSession.objects.get()
    assert registered.identity == linked_user.oidc_identity
    assert registered.sid == "provider-session-123"
    assert registered.session_key == request.session.session_key
    assert registered.session_key != pre_login_session_key
    assert OIDC_SESSION_ISSUER_KEY not in request.session
    assert OIDC_SESSION_SUBJECT_KEY not in request.session
    assert OIDC_SESSION_SID_KEY not in request.session


@pytest.mark.django_db
@override_settings(
    OIDC_ISSUER=ISSUER,
    OIDC_GROUPS_CLAIM="groups",
    OIDC_RP_CLIENT_ID="rent",
    OIDC_RP_CLIENT_SECRET="secret",
    OIDC_OP_TOKEN_ENDPOINT="https://auth.example/token/",
    OIDC_OP_USER_ENDPOINT="https://auth.example/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://auth.example/jwks/",
    OIDC_CREATE_USER=False,
)
@pytest.mark.parametrize("sid", [None, "", True, 123, "x" * 256])
def test_oidc_authentication_fails_closed_for_missing_or_invalid_verified_sid(
    linked_user, sid
):
    """Accepting an unusable verified sid creates a session immune to back-channel logout."""
    request = _oidc_callback_request(code="invalid")

    assert (
        _authenticate_verified_oidc_callback(
            request, linked_user=linked_user, sid=sid
        )
        is None
    )
    assert OIDCSession.objects.count() == 0
    assert OIDC_SESSION_ISSUER_KEY not in request.session
    assert OIDC_SESSION_SUBJECT_KEY not in request.session
    assert OIDC_SESSION_SID_KEY not in request.session


@pytest.mark.django_db
@override_settings(
    OIDC_ISSUER=ISSUER,
    OIDC_GROUPS_CLAIM="groups",
    OIDC_RP_CLIENT_ID="rent",
    OIDC_RP_CLIENT_SECRET="secret",
    OIDC_OP_TOKEN_ENDPOINT="https://auth.example/token/",
    OIDC_OP_USER_ENDPOINT="https://auth.example/userinfo/",
    OIDC_OP_JWKS_ENDPOINT="https://auth.example/jwks/",
    OIDC_CREATE_USER=False,
)
def test_verified_sid_capture_is_isolated_between_unrelated_login_requests(linked_user):
    """Sharing transient sid state between requests binds one user's logout to another."""
    other_user = User.objects.create_user("other-linked-user")
    OIDCIdentity.objects.create(user=other_user, issuer=ISSUER, subject="person-456")
    first_request = _oidc_callback_request(code="first")
    second_request = _oidc_callback_request(code="second")

    first_user = _authenticate_verified_oidc_callback(
        first_request,
        linked_user=linked_user,
        sid="provider-session-first",
        subject="person-123",
    )
    second_user = _authenticate_verified_oidc_callback(
        second_request,
        linked_user=other_user,
        sid="provider-session-second",
        subject="person-456",
    )
    login(first_request, first_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")
    login(second_request, second_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")

    assert set(
        OIDCSession.objects.values_list("identity__subject", "sid", "session_key")
    ) == {
        (
            "person-123",
            "provider-session-first",
            first_request.session.session_key,
        ),
        (
            "person-456",
            "provider-session-second",
            second_request.session.session_key,
        ),
    }


@pytest.mark.django_db
def test_oidc_login_registers_final_rotated_django_session(db, client, linked_user):
    """Removing the login-signal registration must leave no durable session row."""
    from rentals.models import OIDCSession

    session = client.session
    session[OIDC_SESSION_ISSUER_KEY] = ISSUER
    session[OIDC_SESSION_SUBJECT_KEY] = "person-123"
    session[OIDC_SESSION_SID_KEY] = "provider-session-123"
    session.save()

    request = client.request().wsgi_request
    request.session = client.session
    login(request, linked_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")
    client.cookies[settings.SESSION_COOKIE_NAME] = request.session.session_key

    assert OIDCSession.objects.count() == 1
    registered = OIDCSession.objects.get()
    assert registered.identity == linked_user.oidc_identity
    assert registered.sid == "provider-session-123"
    assert registered.session_key == client.session.session_key
    assert OIDC_SESSION_ISSUER_KEY not in request.session
    assert OIDC_SESSION_SUBJECT_KEY not in request.session
    assert OIDC_SESSION_SID_KEY not in request.session


@pytest.mark.django_db
def test_relogin_replaces_same_session_key_association(db, client, linked_user):
    """Dropping the session-key upsert must create duplicate logout targets."""
    from rentals.models import OIDCSession

    request = client.request().wsgi_request
    request.session = client.session
    request.session[OIDC_SESSION_ISSUER_KEY] = ISSUER
    request.session[OIDC_SESSION_SUBJECT_KEY] = "person-123"
    request.session[OIDC_SESSION_SID_KEY] = "provider-session-old"
    request.session.save()
    login(request, linked_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")
    session_key = request.session.session_key
    first_seen = OIDCSession.objects.get().last_seen_at

    request.session[OIDC_SESSION_ISSUER_KEY] = ISSUER
    request.session[OIDC_SESSION_SUBJECT_KEY] = "person-123"
    request.session[OIDC_SESSION_SID_KEY] = "provider-session-new"
    login(request, linked_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")

    assert OIDCSession.objects.count() == 1
    registered = OIDCSession.objects.get()
    assert registered.identity == linked_user.oidc_identity
    assert registered.session_key == session_key
    assert registered.sid == "provider-session-new"
    assert registered.last_seen_at >= first_seen


@pytest.mark.django_db
def test_local_password_login_does_not_create_oidc_session(db, client):
    """Treating every Django login as OIDC would register local sessions."""
    from rentals.models import OIDCSession

    user = User.objects.create_user("local-user", password="local-only-password")
    request = client.request().wsgi_request
    request.session = client.session
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    assert OIDCSession.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "issuer, subject, sid",
    [
        (ISSUER, "person-123", ""),
        (ISSUER, "person-123", None),
        (ISSUER, "missing-identity", "provider-session-123"),
    ],
)
def test_oidc_session_requires_identity_and_nonempty_sid(
    db, client, linked_user, issuer, subject, sid
):
    """Accepting empty sid or an unlinked subject creates unsafe logout state."""
    from rentals.models import OIDCSession

    request = client.request().wsgi_request
    request.session = client.session
    request.session[OIDC_SESSION_ISSUER_KEY] = issuer
    request.session[OIDC_SESSION_SUBJECT_KEY] = subject
    request.session[OIDC_SESSION_SID_KEY] = sid
    request.session.save()
    login(request, linked_user, backend="rentals.oidc.RentalOIDCAuthenticationBackend")

    assert OIDCSession.objects.count() == 0
    assert OIDC_SESSION_ISSUER_KEY not in request.session
    assert OIDC_SESSION_SUBJECT_KEY not in request.session
    assert OIDC_SESSION_SID_KEY not in request.session


@pytest.mark.django_db
def test_oidc_logout_replay_is_unique_per_issuer_and_jti(db):
    """Removing the replay uniqueness constraint permits a logout token replay."""
    from rentals.models import OIDCLogoutReplay
    from django.db import IntegrityError, transaction
    from django.utils import timezone

    OIDCLogoutReplay.objects.create(
        issuer=ISSUER, jti="logout-event-123", expires_at=timezone.now()
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        OIDCLogoutReplay.objects.create(
            issuer=ISSUER, jti="logout-event-123", expires_at=timezone.now()
        )
