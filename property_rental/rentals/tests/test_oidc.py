from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.test import RequestFactory, override_settings
from django.contrib.sessions.middleware import SessionMiddleware

from rentals.models import OIDCIdentity, Property, Tenant, Transaction, User
from rentals.oidc import RentalOIDCAuthenticationBackend, mark_session_authorized
from rentals.tests.factories import PropertyFactory, TenantFactory, TransactionFactory, UserFactory


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
def test_linked_user_profile_syncs_from_life_os_claims_without_changing_identity(backend):
    user = User.objects.create_user(
        "legacy-yaroslav",
        email="old@example.com",
        password="legacy-secret",
        first_name="Old",
        last_name="Name",
    )
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")

    with override_settings(LOCAL_PASSWORD_AUTH_ENABLED=False):
        updated = backend.update_user(
            user,
            {
                "sub": "abc",
                "groups": [VIEWER],
                "preferred_username": "Yaroslav",
                "given_name": "Yaroslav",
                "family_name": "Linik",
                "email": "yaroslav@linik.ru",
            },
        )

    updated.refresh_from_db()
    assert updated.pk == user.pk
    assert updated.username == "Yaroslav"
    assert updated.first_name == "Yaroslav"
    assert updated.last_name == "Linik"
    assert updated.email == "yaroslav@linik.ru"
    assert not updated.has_usable_password()
    assert updated.oidc_identity.subject == "abc"


@pytest.mark.django_db
def test_profile_sync_collision_fails_closed_without_merging_identity(backend):
    existing = UserFactory(username="YL", email="yl@example.com")
    linked = UserFactory(
        username="legacy-yaroslav",
        email="old@example.com",
        first_name="Old",
        last_name="Name",
    )
    OIDCIdentity.objects.create(user=linked, issuer=ISSUER, subject="abc")

    with pytest.raises(SuspiciousOperation, match="OIDC profile synchronization failed"):
        backend.update_user(
            linked,
            {
                "sub": "abc",
                "groups": [VIEWER],
                "preferred_username": existing.username,
                "given_name": "Yaroslav",
                "family_name": "Linik",
                "email": "yaroslav@linik.ru",
            },
        )

    existing.refresh_from_db()
    linked.refresh_from_db()
    assert existing.username == "YL"
    assert linked.username == "legacy-yaroslav"
    assert linked.email == "old@example.com"
    assert linked.oidc_identity.subject == "abc"


@pytest.mark.django_db
def test_profile_sync_preserves_local_pk_and_owned_data_graph(backend):
    user = UserFactory(
        username="Yaroslav",
        email="old@example.com",
        first_name="Old",
        last_name="Name",
        is_landlord=True,
    )
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")
    property_ = PropertyFactory(owned_by=user.landlord)
    tenant = TenantFactory(property=property_, user=None)
    transaction = TransactionFactory(property=property_, tenant=tenant)
    counts = {
        Property: Property.objects.count(),
        Tenant: Tenant.objects.count(),
        Transaction: Transaction.objects.count(),
        User: User.objects.count(),
    }

    backend.update_user(
        user,
        {
            "sub": "abc",
            "groups": [VIEWER],
            "preferred_username": "YL",
            "given_name": "Yaroslav",
            "family_name": "Linik",
            "email": "yaroslav@linik.ru",
        },
    )

    user.refresh_from_db()
    property_.refresh_from_db()
    tenant.refresh_from_db()
    transaction.refresh_from_db()
    assert user.pk == property_.owned_by.user_id
    assert user.username == "YL"
    assert user.first_name == "Yaroslav"
    assert user.last_name == "Linik"
    assert user.email == "yaroslav@linik.ru"
    assert property_.owned_by_id == user.landlord.pk
    assert tenant.property_id == property_.pk
    assert transaction.property_id == property_.pk
    assert transaction.tenant_id == tenant.pk
    assert {
        Property: Property.objects.count(),
        Tenant: Tenant.objects.count(),
        Transaction: Transaction.objects.count(),
        User: User.objects.count(),
    } == counts


@pytest.mark.django_db
def test_profile_sync_preserves_existing_values_for_missing_blank_or_malformed_claims(backend):
    user = User.objects.create_user(
        "existing",
        email="existing@example.com",
        first_name="Existing",
        last_name="Person",
    )
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")

    updated = backend.update_user(
        user,
        {
            "sub": "abc",
            "groups": [VIEWER],
            "preferred_username": "",
            "given_name": None,
            "family_name": 123,
            "email": "not an email address",
        },
    )

    updated.refresh_from_db()
    assert updated.username == "existing"
    assert updated.email == "existing@example.com"
    assert updated.first_name == "Existing"
    assert updated.last_name == "Person"


@pytest.mark.django_db
def test_get_or_create_user_syncs_changed_claims_for_linked_subject(backend):
    user = User.objects.create_user(
        "old-name",
        email="old@example.com",
        first_name="Old",
        last_name="Profile",
    )
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")

    claims = {
        "sub": "abc",
        "groups": [VIEWER],
        "preferred_username": "new-name",
        "given_name": "New",
        "family_name": "Profile",
        "email": "new@example.com",
    }

    with override_settings(OIDC_CREATE_USER=False), patch.object(
        backend, "get_userinfo", return_value=claims
    ), patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims",
        return_value=True,
    ):
        assert backend.get_or_create_user("access", "id", {}) == user

    user.refresh_from_db()
    assert user.username == "new-name"
    assert user.email == "new@example.com"
    assert user.first_name == "New"


@pytest.mark.django_db
def test_userinfo_without_viewer_group_does_not_sync_profile(backend):
    user = User.objects.create_user("old-name", email="old@example.com")
    OIDCIdentity.objects.create(user=user, issuer=ISSUER, subject="abc")
    claims = {
        "sub": "abc",
        "groups": [],
        "preferred_username": "new-name",
        "email": "new@example.com",
    }

    with patch.object(backend, "get_userinfo", return_value=claims), patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims",
        return_value=True,
    ), pytest.raises(SuspiciousOperation, match="Claims verification failed"):
        backend.get_or_create_user("access", "id", {})

    user.refresh_from_db()
    assert user.username == "old-name"
    assert user.email == "old@example.com"


@pytest.mark.django_db
def test_matching_email_does_not_merge_a_local_account(backend):
    local = User.objects.create_user("local", email="person@example.com")

    assert not backend.filter_users_by_claims({"iss": ISSUER, "sub": "new", "email": local.email}).exists()
    oidc_user = backend.create_user({"iss": ISSUER, "sub": "new", "email": local.email})
    assert oidc_user != local


@pytest.mark.django_db
def test_absent_identity_link_does_not_create_or_merge_by_email_when_creation_disabled(backend):
    local = User.objects.create_user("local", email="person@example.com")
    claims = {
        "sub": "unlinked",
        "groups": [VIEWER],
        "preferred_username": "claim-name",
        "email": local.email,
    }

    with override_settings(OIDC_CREATE_USER=False), patch.object(
        backend, "get_userinfo", return_value=claims
    ), patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.verify_claims",
        return_value=True,
    ):
        assert backend.get_or_create_user("access", "id", {}) is None

    local.refresh_from_db()
    assert local.username == "local"
    assert User.objects.count() == 1


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
