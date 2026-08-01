"""Production and build settings contracts."""

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]


def production_environment(**overrides: str) -> dict[str, str]:
    """Return the complete non-secret production environment fixture."""
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "property_rental.settings.prod",
            "DATABASE_URL": "postgresql://rental:secret@db:5432/rental",
            "DJANGO_SECRET_KEY": "test-only-runtime-value",
            "DJANGO_ALLOWED_HOSTS": "rent.linik.ru, www.rent.linik.ru,",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://rent.linik.ru,https://www.rent.linik.ru,",
            "BUSINESS_TIME_ZONE": "Europe/Moscow",
            "OIDC_ISSUER": "https://auth.linik.ru/application/o/rent/",
            "OIDC_CLIENT_ID": "rent-test",
            "OIDC_CLIENT_SECRET": "test-only",
            "OIDC_CALLBACK_URL": "https://rent.linik.ru/oidc/callback/",
            "OIDC_LOGOUT_URL": "https://auth.linik.ru/application/o/rent/end-session/",
        }
    )
    environment.update(overrides)
    return environment


def import_settings(
    environment: dict[str, str],
    expression: str = "settings.DATABASES",
    *,
    setup: bool = False,
) -> subprocess.CompletedProcess[str]:
    setup_code = "import django; django.setup(); " if setup else ""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            setup_code + "from django.conf import settings; import json; "
            "print(json.dumps(" + expression + "))",
        ],
        cwd=PROJECT_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_requires_database_url():
    """Removing DATABASE_URL must prevent production settings from importing."""
    environment = production_environment()
    environment.pop("DATABASE_URL")

    result = import_settings(environment)

    assert result.returncode != 0
    assert "DATABASE_URL" in result.stderr


def test_production_rejects_sqlite_database_url():
    """A SQLite URL must never be accepted by the production database boundary."""
    result = import_settings(production_environment(DATABASE_URL="sqlite:///tmp/rental.sqlite3"))

    assert result.returncode != 0
    assert "PostgreSQL" in result.stderr


def test_production_parses_postgresql_url_into_django_database_settings():
    """A PostgreSQL URL must create Django's PostgreSQL connection configuration."""
    result = import_settings(production_environment())

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "rental",
            "USER": "rental",
            "PASSWORD": "secret",
            "HOST": "db",
            "PORT": "5432",
            "CONN_HEALTH_CHECKS": True,
        }
    }


def test_production_cannot_enable_debug_and_filters_empty_host_entries():
    """DJANGO_DEBUG cannot weaken production, and CSV settings omit empty values."""
    result = import_settings(
        production_environment(DJANGO_DEBUG="True"),
        "{'debug': settings.DEBUG, 'hosts': settings.ALLOWED_HOSTS, 'origins': settings.CSRF_TRUSTED_ORIGINS}",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "debug": False,
        "hosts": ["rent.linik.ru", "www.rent.linik.ru"],
        "origins": ["https://rent.linik.ru", "https://www.rent.linik.ru"],
    }


def test_production_requires_allowed_hosts_and_csrf_trusted_origins():
    """Production host and CSRF boundaries must never silently become empty."""
    for name in ("DJANGO_ALLOWED_HOSTS", "DJANGO_CSRF_TRUSTED_ORIGINS"):
        environment = production_environment()
        environment.pop(name)

        result = import_settings(environment)

        assert result.returncode != 0
        assert name in result.stderr


def test_oidc_callback_and_logout_environment_drive_integration_boundaries():
    """OIDC callback routing and provider logout must consume their env values."""
    result = import_settings(
        production_environment(
            OIDC_CALLBACK_URL="https://rent.linik.ru/identity/callback/",
            OIDC_LOGOUT_URL="https://auth.linik.ru/custom/end-session/",
        ),
        "{'callback': __import__('django.urls').urls.reverse('oidc_authentication_callback'), "
        "'logout_method': settings.OIDC_OP_LOGOUT_URL_METHOD, "
        "'logout_url': __import__('django.utils.module_loading').utils.module_loading.import_string("
        "settings.OIDC_OP_LOGOUT_URL_METHOD)(None)}",
        setup=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "callback": "/identity/callback/",
        "logout_method": "property_rental.oidc.provider_logout_url",
        "logout_url": "https://auth.linik.ru/custom/end-session/",
    }


def test_oidc_provider_endpoints_can_be_configured_independently_from_issuer():
    """Some providers expose a provider-specific issuer but shared OAuth endpoints."""
    result = import_settings(
        production_environment(
            OIDC_ISSUER="https://auth.linik.ru/application/o/lifeos-rent/",
            OIDC_AUTHORIZATION_ENDPOINT="https://auth.linik.ru/application/o/authorize/",
            OIDC_TOKEN_ENDPOINT="https://auth.linik.ru/application/o/token/",
            OIDC_USERINFO_ENDPOINT="https://auth.linik.ru/application/o/userinfo/",
            OIDC_JWKS_ENDPOINT="https://auth.linik.ru/application/o/lifeos-rent/jwks/",
        ),
        "{'issuer': settings.OIDC_ISSUER, "
        "'authorize': settings.OIDC_OP_AUTHORIZATION_ENDPOINT, "
        "'token': settings.OIDC_OP_TOKEN_ENDPOINT, "
        "'userinfo': settings.OIDC_OP_USER_ENDPOINT, "
        "'jwks': settings.OIDC_OP_JWKS_ENDPOINT}",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "issuer": "https://auth.linik.ru/application/o/lifeos-rent/",
        "authorize": "https://auth.linik.ru/application/o/authorize/",
        "token": "https://auth.linik.ru/application/o/token/",
        "userinfo": "https://auth.linik.ru/application/o/userinfo/",
        "jwks": "https://auth.linik.ru/application/o/lifeos-rent/jwks/",
    }


def test_production_requests_and_reads_the_life_os_role_claim():
    """Rent authorization must consume the scoped role contract issued by Life OS."""
    result = import_settings(
        production_environment(),
        "{'scopes': settings.OIDC_RP_SCOPES, 'claim': settings.OIDC_GROUPS_CLAIM}",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "scopes": "openid email profile lifeos_roles",
        "claim": "https://linik.ru/claims/roles",
    }


def test_life_os_profile_url_is_optional_and_accepts_only_linik_profile_origin():
    """The central profile link is optional until Life OS ships linik.ru/profile."""
    unset_environment = production_environment()
    unset_environment.pop("LIFE_OS_PROFILE_URL", None)

    unset = import_settings(unset_environment, "settings.LIFE_OS_PROFILE_URL")
    valid = import_settings(
        production_environment(LIFE_OS_PROFILE_URL="https://linik.ru/profile"),
        "settings.LIFE_OS_PROFILE_URL",
    )

    assert unset.returncode == 0, unset.stderr
    assert json.loads(unset.stdout) is None
    assert valid.returncode == 0, valid.stderr
    assert json.loads(valid.stdout) == "https://linik.ru/profile"


def test_life_os_profile_url_rejects_insecure_authentik_and_unapproved_origins():
    """Rent must not invent Authentik dashboard/security-flow links."""
    for url in (
        "http://linik.ru/profile",
        "https://auth.linik.ru/if/user/",
        "https://profile.linik.ru/",
        "https://evil.example/profile",
    ):
        result = import_settings(production_environment(LIFE_OS_PROFILE_URL=url))

        assert result.returncode != 0
        assert "LIFE_OS_PROFILE_URL" in result.stderr


def test_production_urlconf_preserves_custom_not_found_handler():
    """Production must retain the project's plain API 404 response handler."""
    result = import_settings(
        production_environment(),
        "{'module': __import__(settings.ROOT_URLCONF, fromlist=['handler404']).handler404.__module__, "
        "'name': __import__(settings.ROOT_URLCONF, fromlist=['handler404']).handler404.__name__}",
        setup=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "module": "property_rental.urls",
        "name": "api_not_found",
    }


def test_production_configures_oidc_pkce_and_security_contracts():
    """Production must retain OIDC PKCE and HTTPS proxy/cookie/header protections."""
    result = import_settings(
        production_environment(),
        "{'pkce': settings.OIDC_USE_PKCE, 'method': settings.OIDC_PKCE_CODE_CHALLENGE_METHOD, "
        "'create_user': settings.OIDC_CREATE_USER, "
        "'proxy': settings.SECURE_PROXY_SSL_HEADER, 'session_secure': settings.SESSION_COOKIE_SECURE, "
        "'csrf_secure': settings.CSRF_COOKIE_SECURE, 'hsts': settings.SECURE_HSTS_SECONDS, "
        "'referrer': settings.SECURE_REFERRER_POLICY, 'cors': hasattr(settings, 'CORS_ALLOWED_ORIGINS')}",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "pkce": True,
        "method": "S256",
        "create_user": False,
        "proxy": ["HTTP_X_FORWARDED_PROTO", "https"],
        "session_secure": True,
        "csrf_secure": True,
        "hsts": 31536000,
        "referrer": "same-origin",
        "cors": False,
    }


def test_production_health_paths_skip_oidc_session_refresh():
    """Authenticated OIDC sessions must not make health checks refreshable."""
    code = """
import django
import json
from django.conf import settings
from django.test import RequestFactory
from django.utils.module_loading import import_string

django.setup()

middleware_path = next(
    path for path in settings.MIDDLEWARE
    if path.endswith('HealthCheckSessionRefresh')
)
middleware = import_string(middleware_path)(lambda request: None)
factory = RequestFactory()
results = {}
for path in ('/health/live', '/health/ready'):
    request = factory.get(path)
    request.user = type(
        'DatabaseTouchingUser',
        (),
        {'is_authenticated': property(lambda self: (_ for _ in ()).throw(AssertionError()))},
    )()
    request.session = {
        '_auth_user_backend': 'rentals.oidc.RentalOIDCAuthenticationBackend'
    }
    results[path] = middleware.is_refreshable_url(request)
print(json.dumps(results))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_DIR,
        env=production_environment(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "/health/live": False,
        "/health/ready": False,
    }


def test_build_settings_need_no_runtime_secrets_but_require_vite_manifest():
    """Build settings avoid runtime secrets but stop collection without Vite output."""
    manifest_path = PROJECT_DIR / "rentals/static/frontend/manifest.json"
    original_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = "property_rental.settings.build"
    for name in (
        "DATABASE_URL",
        "DJANGO_SECRET_KEY",
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_CALLBACK_URL",
        "OIDC_LOGOUT_URL",
    ):
        environment.pop(name, None)

    try:
        manifest_path.unlink(missing_ok=True)
        result = import_settings(environment, "settings.DJANGO_VITE")
    finally:
        if original_manifest is not None:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_bytes(original_manifest)

    assert result.returncode != 0
    assert "manifest.json" in result.stderr


def test_postgres_settings_do_not_require_vite_manifest_for_backend_ci():
    """Backend-only PostgreSQL CI must render the SPA shell before frontend build."""
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "property_rental.settings.test_postgres",
            "DATABASE_URL": "postgresql://property_rental_ci:property_rental_ci@127.0.0.1:5432/property_rental_ci",
        }
    )

    result = import_settings(
        environment,
        "settings.DJANGO_VITE['default']['dev_mode']",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) is True
