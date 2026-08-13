from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from rentals.models import OIDCIdentity, OIDCLogoutReplay, OIDCSession, User
from rentals.tests.factories import LandlordFactory, PropertyFactory


@pytest.fixture
def stale_oidc_state(db):
    user = User.objects.create_user("maintenance-user")
    identity = OIDCIdentity.objects.create(
        user=user,
        issuer="https://auth.example/application/o/rent/",
        subject="maintenance-subject",
    )
    landlord = LandlordFactory(user=user)
    property_record = PropertyFactory(owned_by=landlord)
    expire_date = timezone.now() + timedelta(hours=1)
    referenced_keys = ["a" * 40, "b" * 40]
    sids = ["provider-session-a", "provider-session-b"]
    for session_key, sid in zip(referenced_keys, sids, strict=True):
        Session.objects.create(
            session_key=session_key,
            session_data="",
            expire_date=expire_date,
        )
        OIDCSession.objects.create(
            identity=identity,
            sid=sid,
            session_key=session_key,
        )
    unrelated_key = "c" * 40
    Session.objects.create(
        session_key=unrelated_key,
        session_data="",
        expire_date=expire_date,
    )
    replay = OIDCLogoutReplay.objects.create(
        issuer=identity.issuer,
        jti="maintenance-replay",
        expires_at=expire_date,
    )
    return {
        "identity": identity,
        "property": property_record,
        "referenced_keys": referenced_keys,
        "replay": replay,
        "sids": sids,
        "unrelated_key": unrelated_key,
    }


@pytest.mark.django_db
def test_dry_run_reports_counts_without_deleting_or_exposing_identifiers(stale_oidc_state):
    stdout = StringIO()
    call_command("purge_oidc_sessions", stdout=stdout)
    assert stdout.getvalue().strip() == (
        "action=dry-run oidc_associations=2 referenced_django_sessions=2"
    )
    assert OIDCSession.objects.count() == 2
    assert Session.objects.filter(
        session_key__in=stale_oidc_state["referenced_keys"]
    ).count() == 2
    sensitive_values = [
        *stale_oidc_state["referenced_keys"],
        *stale_oidc_state["sids"],
        stale_oidc_state["identity"].subject,
    ]
    for secret_value in sensitive_values:
        assert secret_value not in stdout.getvalue()


@pytest.mark.django_db
def test_confirmed_purge_deletes_only_selected_associations_and_referenced_sessions(stale_oidc_state):
    stdout = StringIO()
    call_command("purge_oidc_sessions", confirm_all_current=True, stdout=stdout)
    assert stdout.getvalue().strip() == (
        "action=purged oidc_associations=2 referenced_django_sessions=2"
    )
    assert OIDCSession.objects.count() == 0
    assert Session.objects.filter(
        session_key__in=stale_oidc_state["referenced_keys"]
    ).count() == 0
    assert Session.objects.filter(
        session_key=stale_oidc_state["unrelated_key"]
    ).exists()
    assert OIDCIdentity.objects.filter(pk=stale_oidc_state["identity"].pk).exists()
    assert OIDCLogoutReplay.objects.filter(pk=stale_oidc_state["replay"].pk).exists()
    assert type(stale_oidc_state["property"]).objects.filter(
        pk=stale_oidc_state["property"].pk
    ).exists()


@pytest.mark.django_db
def test_confirmed_purge_is_idempotent(stale_oidc_state):
    call_command("purge_oidc_sessions", confirm_all_current=True)
    stdout = StringIO()
    call_command("purge_oidc_sessions", confirm_all_current=True, stdout=stdout)
    assert stdout.getvalue().strip() == (
        "action=purged oidc_associations=0 referenced_django_sessions=0"
    )
