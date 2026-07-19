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
