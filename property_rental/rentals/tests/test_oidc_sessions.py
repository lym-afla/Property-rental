import pytest
from django.conf import settings
from django.contrib.auth import login
from django.test import Client

from rentals.models import OIDCIdentity, User
from rentals.oidc import (
    OIDC_SESSION_ISSUER_KEY,
    OIDC_SESSION_SID_KEY,
    OIDC_SESSION_SUBJECT_KEY,
)


ISSUER = "https://auth.example/application/o/rent/"


@pytest.fixture
def linked_user(db):
    user = User.objects.create_user("linked-user")
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="person-123")
    return user


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
