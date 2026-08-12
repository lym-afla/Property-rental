from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import Client, RequestFactory
from django.utils import timezone
from django.views.debug import SafeExceptionReporterFilter

from rentals.models import OIDCIdentity, OIDCLogoutReplay, OIDCSession, User


ISSUER = "https://auth.example/application/o/rent/"
OTHER_ISSUER = "https://other-auth.example/application/o/rent/"
BACKCHANNEL_LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"
ORIGINAL_GET_SIGNING_KEY_FROM_JWT = jwt.PyJWKClient.get_signing_key_from_jwt


@pytest.fixture
def signing_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture(autouse=True)
def oidc_logout_settings(settings, monkeypatch, signing_keys):
    settings.OIDC_ISSUER = ISSUER
    settings.OIDC_RP_CLIENT_ID = "rent"
    settings.OIDC_OP_JWKS_ENDPOINT = "https://auth.example/application/o/rent/jwks/"
    settings.OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS = 300
    settings.OIDC_CALLBACK_URL = "http://testserver/oidc/callback/"
    settings.ROOT_URLCONF = "property_rental.production_urls"
    monkeypatch.setattr(
        jwt.PyJWKClient,
        "get_signing_key_from_jwt",
        lambda self, encoded: SimpleNamespace(key=signing_keys[1]),
    )


def make_logout_token(
    private_key,
    *,
    issuer=ISSUER,
    audience="rent",
    issued_at=None,
    jti="logout-event-1",
    sid="provider-session-1",
    subject="person-1",
    events=None,
    extra_claims=None,
):
    claims = {
        "iss": issuer,
        "aud": audience,
        "iat": issued_at or timezone.now(),
        "jti": jti,
        "events": (
            {BACKCHANNEL_LOGOUT_EVENT: {}}
            if events is None
            else events
        ),
    }
    if sid is not None:
        claims["sid"] = sid
    if subject is not None:
        claims["sub"] = subject
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def register_session(*, issuer=ISSUER, subject="person-1", sid="provider-session-1"):
    identity = OIDCIdentity.objects.filter(issuer=issuer, subject=subject).first()
    if identity is None:
        user = User.objects.create_user(f"user-{User.objects.count() + 1}")
        identity = OIDCIdentity.objects.create(user=user, issuer=issuer, subject=subject)
    session = SessionStore()
    session["authenticated"] = True
    session.save()
    registered = OIDCSession.objects.create(
        identity=identity,
        sid=sid,
        session_key=session.session_key,
    )
    return registered


def post_logout(client, token):
    return client.post("/oidc/backchannel-logout/", {"logout_token": token})


@pytest.mark.django_db
def test_valid_sid_logout_deletes_only_matching_django_session(client, signing_keys):
    matching = register_session()
    other_sid = register_session(subject="person-2", sid="provider-session-2")
    other_issuer = register_session(issuer=OTHER_ISSUER)

    response = post_logout(client, make_logout_token(signing_keys[0]))

    assert response.status_code == 200
    assert not Session.objects.filter(session_key=matching.session_key).exists()
    assert not OIDCSession.objects.filter(pk=matching.pk).exists()
    assert Session.objects.filter(session_key=other_sid.session_key).exists()
    assert OIDCSession.objects.filter(pk=other_sid.pk).exists()
    assert Session.objects.filter(session_key=other_issuer.session_key).exists()
    assert OIDCSession.objects.filter(pk=other_issuer.pk).exists()


@pytest.mark.django_db
def test_valid_subject_only_logout_deletes_all_subject_sessions(client, signing_keys):
    first = register_session(sid="provider-session-1")
    second = register_session(sid="provider-session-2")
    other_subject = register_session(subject="person-2", sid="provider-session-3")
    token = make_logout_token(signing_keys[0], sid=None)

    response = post_logout(client, token)

    assert response.status_code == 200
    assert not Session.objects.filter(session_key__in=[first.session_key, second.session_key]).exists()
    assert not OIDCSession.objects.filter(pk__in=[first.pk, second.pk]).exists()
    assert Session.objects.filter(session_key=other_subject.session_key).exists()
    assert OIDCSession.objects.filter(pk=other_subject.pk).exists()


@pytest.mark.django_db
def test_repeated_valid_logout_is_idempotent(client, signing_keys):
    registered = register_session()
    token = make_logout_token(signing_keys[0])

    first = post_logout(client, token)
    second = post_logout(client, token)

    assert first.status_code == second.status_code == 200
    assert not OIDCSession.objects.filter(pk=registered.pk).exists()
    assert OIDCLogoutReplay.objects.filter(issuer=ISSUER, jti="logout-event-1").count() == 1


@pytest.mark.django_db(transaction=True)
def test_replayed_jti_does_not_repeat_session_work(signing_keys):
    from rentals.oidc_logout import invalidate_oidc_sessions, validate_logout_token

    first = register_session()
    claims = validate_logout_token(make_logout_token(signing_keys[0]))

    assert invalidate_oidc_sessions(claims) == 1
    assert not OIDCSession.objects.filter(pk=first.pk).exists()

    replacement = register_session()

    assert invalidate_oidc_sessions(claims) == 0
    assert OIDCSession.objects.filter(pk=replacement.pk).exists()
    assert Session.objects.filter(session_key=replacement.session_key).exists()


def assert_wrong_claim_is_rejected_without_deleting_sessions(
    client, signing_keys, claim, value
):
    registered = register_session()
    token = make_logout_token(signing_keys[0], **{claim: value})

    response = post_logout(client, token)

    assert response.status_code == 400
    assert Session.objects.filter(session_key=registered.session_key).exists()
    assert OIDCSession.objects.filter(pk=registered.pk).exists()
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_wrong_issuer_is_rejected_without_deleting_sessions(client, signing_keys):
    assert_wrong_claim_is_rejected_without_deleting_sessions(
        client, signing_keys, "issuer", OTHER_ISSUER
    )


@pytest.mark.django_db
def test_wrong_audience_is_rejected_without_deleting_sessions(client, signing_keys):
    assert_wrong_claim_is_rejected_without_deleting_sessions(
        client, signing_keys, "audience", "other-client"
    )


@pytest.mark.django_db
def test_wrong_signature_is_rejected_without_deleting_sessions(client, signing_keys):
    registered = register_session()
    untrusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    response = post_logout(client, make_logout_token(untrusted_key))

    assert response.status_code == 400
    assert Session.objects.filter(session_key=registered.session_key).exists()
    assert OIDCSession.objects.filter(pk=registered.pk).exists()
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_missing_logout_event_is_rejected(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], events={}),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_missing_sid_and_sub_is_rejected(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], sid=None, subject=None),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_stale_iat_is_rejected(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], issued_at=timezone.now() - timedelta(seconds=301)),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "claims",
    [
        {"sid": True},
        {"sid": 123},
        {"subject": True, "sid": None},
        {"subject": 123, "sid": None},
        {"jti": True},
        {"jti": 123},
        {"jti": ""},
    ],
)
def test_boolean_non_string_and_empty_identifiers_are_rejected(client, signing_keys, claims):
    response = post_logout(client, make_logout_token(signing_keys[0], **claims))

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_future_iat_beyond_clock_skew_is_rejected(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], issued_at=timezone.now() + timedelta(seconds=61)),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_out_of_range_iat_is_rejected(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], issued_at=10**100),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "claims",
    [
        {"jti": "x" * 256},
        {"sid": "x" * 256},
        {"subject": "x" * 256, "sid": None},
    ],
)
def test_identifiers_larger_than_registry_fields_are_rejected(
    client, signing_keys, claims
):
    response = post_logout(client, make_logout_token(signing_keys[0], **claims))

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


def test_jwks_client_is_reused_between_validations(settings, monkeypatch, signing_keys):
    from rentals.oidc_logout import _get_jwk_client, validate_logout_token

    clients_seen = set()

    def resolve_from_test_key(client, encoded):
        clients_seen.add(id(client))
        return SimpleNamespace(key=signing_keys[1])

    _get_jwk_client.cache_clear()
    monkeypatch.setattr(jwt.PyJWKClient, "get_signing_key_from_jwt", resolve_from_test_key)

    validate_logout_token(make_logout_token(signing_keys[0], jti="logout-event-1"))
    validate_logout_token(make_logout_token(signing_keys[0], jti="logout-event-2"))

    assert len(clients_seen) == 1


def test_jwks_fetch_identifies_rent_to_the_public_auth_boundary(
    settings, monkeypatch, signing_keys
):
    """Removing Rent's explicit JWKS user agent must break key discovery."""
    from rentals.oidc_logout import _get_jwk_client, validate_logout_token

    expected_user_agent = "LifeOS-Rent-OIDC/1.0"
    public_jwk = RSAAlgorithm.to_jwk(signing_keys[1], as_dict=True)
    public_jwk["kid"] = "test-key"

    class JwksHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("User-Agent") != expected_user_agent:
                self.send_response(403)
                self.end_headers()
                return
            body = json.dumps({"keys": [public_jwk]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), JwksHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.OIDC_OP_JWKS_ENDPOINT = (
        f"http://127.0.0.1:{server.server_address[1]}/jwks/"
    )
    _get_jwk_client.cache_clear()
    monkeypatch.setattr(
        jwt.PyJWKClient,
        "get_signing_key_from_jwt",
        ORIGINAL_GET_SIGNING_KEY_FROM_JWT,
    )

    try:
        claims = validate_logout_token(make_logout_token(signing_keys[0]))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        _get_jwk_client.cache_clear()

    assert claims.sid == "provider-session-1"


@pytest.mark.django_db
def test_rejected_logout_logs_only_a_bounded_reason_code(
    client, signing_keys, caplog
):
    """Replacing safe reason codes with silence or token details must fail."""
    token = make_logout_token(
        signing_keys[0],
        extra_claims={"nonce": "sensitive-diagnostic-marker"},
    )

    with caplog.at_level("WARNING", logger="rentals.api.oidc_logout"):
        response = post_logout(client, token)

    assert response.status_code == 400
    matching = []
    for record in caplog.records:
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "oidc_backchannel_logout_rejected":
            matching.append(payload)
    assert len(matching) == 1
    assert matching[0] == {
        "event": "oidc_backchannel_logout_rejected",
        "reason_code": "nonce",
    }
    rendered = "\n".join(caplog.messages)
    assert token not in rendered
    assert "sensitive-diagnostic-marker" not in rendered


@pytest.mark.django_db
def test_logout_event_value_must_be_empty_object(client, signing_keys):
    response = post_logout(
        client,
        make_logout_token(signing_keys[0], events={BACKCHANNEL_LOGOUT_EVENT: {"unexpected": True}}),
    )

    assert response.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_nonce_claim_is_rejected_without_logout_side_effects(client, signing_keys):
    """Accepting nonce violates the OIDC back-channel logout token contract."""
    registered = register_session()

    response = post_logout(
        client,
        make_logout_token(signing_keys[0], extra_claims={"nonce": "not-allowed"}),
    )

    assert response.status_code == 400
    assert Session.objects.filter(session_key=registered.session_key).exists()
    assert OIDCSession.objects.filter(pk=registered.pk).exists()
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_endpoint_requires_form_logout_token(client, signing_keys):
    token = make_logout_token(signing_keys[0])

    missing = client.post("/oidc/backchannel-logout/", {})
    json_body = client.post(
        "/oidc/backchannel-logout/",
        {"logout_token": token},
        content_type="application/json",
    )

    assert missing.status_code == 400
    assert json_body.status_code == 400
    assert OIDCLogoutReplay.objects.count() == 0


@pytest.mark.django_db
def test_endpoint_needs_no_browser_cookie_or_csrf_token(signing_keys):
    registered = register_session()
    anonymous_client = Client(enforce_csrf_checks=True)

    response = post_logout(anonymous_client, make_logout_token(signing_keys[0]))

    assert response.status_code == 200
    assert not OIDCSession.objects.filter(pk=registered.pk).exists()


@pytest.mark.django_db
def test_endpoint_response_contains_no_identity_or_token_material(client, signing_keys):
    register_session()
    token = make_logout_token(signing_keys[0])

    response = post_logout(client, token)

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "person-1" not in str(response.headers)
    assert "provider-session-1" not in str(response.headers)
    assert token not in str(response.headers)


def test_exception_report_filter_hides_logout_token(monkeypatch):
    from rentals.api.oidc_logout import BackChannelLogoutView

    submitted_value = "sensitive-" + "post-value"
    request = RequestFactory().post(
        "/oidc/backchannel-logout/",
        {"logout_token": submitted_value},
    )

    def raise_unexpected_error(raw_token):
        raise RuntimeError("exception-report-filter-probe")

    monkeypatch.setattr(
        "rentals.api.oidc_logout.validate_logout_token",
        raise_unexpected_error,
    )

    with pytest.raises(RuntimeError, match="exception-report-filter-probe"):
        BackChannelLogoutView.as_view()(request)

    filtered = SafeExceptionReporterFilter().get_post_parameters(request)
    assert filtered["logout_token"] == "********************"
    assert submitted_value not in str(filtered)


@pytest.mark.django_db
@pytest.mark.parametrize("claim", ["exp", "nbf"])
def test_signed_malformed_optional_claim_is_rejected_without_deleting_sessions(
    signing_keys, claim
):
    from rentals.api.oidc_logout import BackChannelLogoutView

    registered = register_session()
    request = RequestFactory().post(
        "/oidc/backchannel-logout/",
        {
            "logout_token": make_logout_token(
                signing_keys[0],
                extra_claims={claim: None},
            )
        },
    )

    try:
        response = BackChannelLogoutView.as_view()(request)
    except Exception as error:
        response = error

    assert getattr(response, "status_code", None) == 400
    assert Session.objects.filter(session_key=registered.session_key).exists()
    assert OIDCSession.objects.filter(pk=registered.pk).exists()
    assert OIDCLogoutReplay.objects.count() == 0
