"""TDD tests for the auth endpoints (Task 4).

These tests are written BEFORE the views exist, so the initial run
should fail with 404 / NoReverseMatch. After implementing the
``LoginView`` / ``LogoutView`` / ``MeView`` and wiring them under
``/api/v1/auth/``, all five tests should pass.

Endpoints under test:

* ``POST /api/v1/auth/login/``  — body ``{username, password}`` →
  ``200 {user: {...}}`` (sets ``sessionid`` cookie) or
  ``400 {detail: "Invalid credentials"}``.
* ``POST /api/v1/auth/logout/`` — ``204`` (clears session).
* ``GET  /api/v1/auth/me/``     — ``200 {user: {...}}`` when
  authenticated, otherwise ``401``.
"""

import pytest
from django.test import override_settings
from django.test import Client

from rentals.tests.factories import UserFactory


@pytest.mark.django_db
def test_login_success_returns_user(db):
    user = UserFactory(username="alice", is_landlord=True)
    user.set_password("TestPass123!")
    user.save()
    c = Client()
    resp = c.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": "TestPass123!"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["is_landlord"] is True
    # Session cookie set
    assert "sessionid" in resp.cookies


@pytest.mark.django_db
def test_login_invalid_credentials_returns_400(db):
    c = Client()
    resp = c.post(
        "/api/v1/auth/login/",
        {"username": "ghost", "password": "wrong"},
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


@pytest.mark.django_db
def test_me_requires_auth(db):
    c = Client()
    resp = c.get("/api/v1/auth/me/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_me_returns_user_when_authenticated(db):
    user = UserFactory(is_landlord=True)
    c = Client()
    c.force_login(user)
    resp = c.get("/api/v1/auth/me/")
    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == user.id


@pytest.mark.django_db
def test_logout_clears_session(db):
    user = UserFactory(is_landlord=True)
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/logout/")
    assert resp.status_code == 204
    # Subsequent /me should 401
    resp2 = c.get("/api/v1/auth/me/")
    assert resp2.status_code in (401, 403)


# --- Register endpoint (Task 5) ---------------------------------------------

@pytest.mark.django_db
def test_register_creates_user_and_logs_in(db):
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "newlandlord",
        "password": "StrongPass123!",
        "email": "new@example.com",
    }, content_type="application/json")
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["username"] == "newlandlord"
    # Session cookie set (auto-login)
    assert "sessionid" in resp.cookies
    # Landlord auto-created (Phase 1 behavior: User.save() creates Landlord when is_landlord=True)
    # Registration should set is_landlord=True by default
    from rentals.models import User
    u = User.objects.get(username="newlandlord")
    assert u.is_landlord is True

@pytest.mark.django_db
def test_register_rejects_duplicate_username(db):
    UserFactory(username="taken")
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "taken",
        "password": "StrongPass123!",
        "email": "x@example.com",
    }, content_type="application/json")
    assert resp.status_code == 400
    assert "username" in resp.json()

@pytest.mark.django_db
def test_register_rejects_weak_password(db):
    c = Client()
    resp = c.post("/api/v1/auth/register/", {
        "username": "newlandlord",
        "password": "1",  # fails validators
        "email": "new@example.com",
    }, content_type="application/json")
    assert resp.status_code == 400
    assert "password" in resp.json()


# --- CSRF cookie endpoint (Task 13) -----------------------------------------

@pytest.mark.django_db
def test_csrf_endpoint_sets_cookie(db):
    """``GET /api/v1/auth/csrf/`` must stamp the ``csrftoken`` cookie.

    Django's ``CsrfViewMiddleware`` only sets the cookie on HTML responses;
    the SPA only receives JSON, so without this endpoint the SPA's first
    mutation is rejected with 403. The ``@ensure_csrf_cookie`` decorator on
    ``CsrfView`` forces the cookie onto the JSON response.
    """
    c = Client()
    resp = c.get("/api/v1/auth/csrf/")
    assert resp.status_code == 200
    # The cookie must be present on the response.
    assert "csrftoken" in resp.cookies, (
        "CsrfView must set the csrftoken cookie via @ensure_csrf_cookie"
    )
    # And the cookie value must be non-empty (a blank value would not be
    # usable as the X-CSRFToken header for subsequent mutations).
    assert resp.cookies["csrftoken"].value, (
        "csrftoken cookie value must be non-empty"
    )


# --- PATCH /me/ and change-password (Task 8) --------------------------------

@pytest.mark.django_db
def test_patch_me_updates_settings(db):
    user = UserFactory(is_landlord=True, chart_frequency='M')
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.patch("/api/v1/auth/me/", {"chart_frequency": "Q"}, content_type="application/json")
    assert resp.status_code == 200
    assert resp.json()["user"]["chart_frequency"] == "Q"
    user.refresh_from_db()
    assert user.chart_frequency == "Q"


@pytest.mark.django_db
def test_patch_me_rejects_life_os_identity_field_updates(db):
    user = UserFactory(
        username="central-user",
        email="central@example.com",
        first_name="Central",
        last_name="Owner",
        is_landlord=True,
    )
    c = Client()
    c.force_login(user)

    resp = c.patch(
        "/api/v1/auth/me/",
        {
            "username": "local-takeover",
            "email": "changed@example.com",
            "first_name": "Changed",
            "last_name": "Locally",
        },
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert resp.json() == {
        "username": ["This field is managed by Life OS."],
        "email": ["This field is managed by Life OS."],
        "first_name": ["This field is managed by Life OS."],
        "last_name": ["This field is managed by Life OS."],
    }
    user.refresh_from_db()
    assert user.username == "central-user"
    assert user.email == "central@example.com"
    assert user.first_name == "Central"
    assert user.last_name == "Owner"


@pytest.mark.django_db
def test_patch_me_cannot_change_role(db):
    """``PATCH /auth/me/`` must NOT let a client flip role flags.

    Phase 4 Task 6 (2026-07-19): ``is_landlord`` / ``is_tenant`` /
    ``id`` / ``username`` are listed as ``read_only_fields`` on
    ``UserSerializer``. The PATCH view passes the payload through the
    serializer with ``partial=True``; without the read-only marking, a
    tenant could escalate to landlord (and gain landlord-only API
    access) by sending ``{"is_landlord": true}``, or hijack another
    account by PATCHing ``{"id": <other_user_id>}``.

    The serializer MUST accept the request (200) — read-only fields
    are silently ignored by DRF, not rejected — but the database value
    must NOT change. ``user.refresh_from_db()`` confirms the persisted
    flag is unchanged after the PATCH round-trip.
    """
    from rentals.models import User

    user = UserFactory(is_landlord=True)
    c = Client()
    c.force_login(user)
    resp = c.patch(
        "/api/v1/auth/me/",
        {"is_landlord": False},
        content_type="application/json",
    )
    # DRF silently drops read-only fields from validated_data, so the
    # request succeeds with 200 — the security contract is that the
    # value is preserved, not that the request is rejected.
    assert resp.status_code == 200, (
        f"PATCH /auth/me/ with a read-only field should still return 200 "
        f"(serializer silently ignores it); got {resp.status_code}"
    )
    user.refresh_from_db()
    assert user.is_landlord is True, (
        "is_landlord is read_only on UserSerializer; PATCH must not flip it"
    )

    # Defense-in-depth: also confirm the read-only fields reject direct
    # writes at the serializer layer (the structural guarantee the
    # test above relies on). A future change to ``read_only_fields``
    # that drops ``is_landlord`` would fail here too.
    from rentals.api.serializers import UserSerializer

    serializer = UserSerializer(user, data={"is_landlord": False, "id": 99999}, partial=True)
    serializer.is_valid(raise_exception=True)
    assert "is_landlord" not in serializer.validated_data, (
        "is_landlord must be in read_only_fields and excluded from validated_data"
    )
    assert "id" not in serializer.validated_data, (
        "id must be in read_only_fields and excluded from validated_data"
    )


@pytest.mark.django_db
def test_change_password_success(db):
    user = UserFactory(is_landlord=True)
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/change-password/", {
        "old_password": "OldPass123!",
        "new_password1": "NewPass456!",
        "new_password2": "NewPass456!",
    }, content_type="application/json")
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.check_password("NewPass456!")


@pytest.mark.django_db
def test_change_password_wrong_old_returns_400(db):
    user = UserFactory(is_landlord=True)
    user.set_password("OldPass123!")
    user.save()
    c = Client()
    c.force_login(user)
    resp = c.post("/api/v1/auth/change-password/", {
        "old_password": "WrongPass!",
        "new_password1": "NewPass456!",
        "new_password2": "NewPass456!",
    }, content_type="application/json")
    assert resp.status_code == 400


@pytest.mark.django_db
@override_settings(LOCAL_PASSWORD_AUTH_ENABLED=False)
def test_production_profile_omits_and_ignores_effective_date(db):
    user = UserFactory(is_landlord=True, effective_date="2025-01-02")
    from rentals.api.serializers import UserSerializer

    serializer = UserSerializer(
        user,
        data={"effective_date": "2040-12-31"},
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    assert "effective_date" not in serializer.data
    user.refresh_from_db()
    assert user.effective_date.isoformat() == "2025-01-02"
