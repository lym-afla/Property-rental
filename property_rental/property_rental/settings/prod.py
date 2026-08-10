"""Strict production settings, with all runtime configuration from the environment."""

from .base import *  # noqa
from .env import csv_env, optional_https_url_env, postgres_database, required_env


DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
TIME_ZONE = required_env("BUSINESS_TIME_ZONE")
DATABASES = {"default": postgres_database(required_env("DATABASE_URL"))}

AUTHENTICATION_BACKENDS = [
    "rentals.oidc.RentalOIDCAuthenticationBackend",
]
OIDC_ISSUER = required_env("OIDC_ISSUER")
OIDC_RP_CLIENT_ID = required_env("OIDC_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = required_env("OIDC_CLIENT_SECRET")
OIDC_CALLBACK_URL = required_env("OIDC_CALLBACK_URL")
OIDC_LOGOUT_URL = required_env("OIDC_LOGOUT_URL")
ROOT_URLCONF = "property_rental.production_urls"
_OIDC_ENDPOINT_BASE = OIDC_ISSUER.rstrip("/")
OIDC_OP_AUTHORIZATION_ENDPOINT = os.environ.get(
    "OIDC_AUTHORIZATION_ENDPOINT", f"{_OIDC_ENDPOINT_BASE}/authorize/"
)
OIDC_OP_TOKEN_ENDPOINT = os.environ.get(
    "OIDC_TOKEN_ENDPOINT", f"{_OIDC_ENDPOINT_BASE}/token/"
)
OIDC_OP_USER_ENDPOINT = os.environ.get(
    "OIDC_USERINFO_ENDPOINT", f"{_OIDC_ENDPOINT_BASE}/userinfo/"
)
OIDC_OP_JWKS_ENDPOINT = os.environ.get(
    "OIDC_JWKS_ENDPOINT", f"{_OIDC_ENDPOINT_BASE}/jwks/"
)
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_USE_PKCE = True
OIDC_PKCE_CODE_CHALLENGE_METHOD = "S256"
OIDC_OP_LOGOUT_URL_METHOD = "property_rental.oidc.provider_logout_url"
OIDC_ALLOWED_REDIRECT_HOSTS = ALLOWED_HOSTS
OIDC_STORE_ACCESS_TOKEN = False
OIDC_STORE_ID_TOKEN = False
OIDC_CREATE_USER = False
OIDC_EXEMPT_URLS = ("/health/live", "/health/ready")
OIDC_AUTHORIZATION_MAX_AGE = int(os.environ.get("OIDC_AUTHORIZATION_MAX_AGE", "300"))
OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS = int(
    os.environ.get("OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS", "300")
)
LIFE_OS_PROFILE_URL = optional_https_url_env(
    "LIFE_OS_PROFILE_URL",
    allowed_origins={"https://linik.ru"},
)
LOCAL_PASSWORD_AUTH_ENABLED = os.environ.get(
    "LOCAL_PASSWORD_AUTH_ENABLED", "false"
).lower() in {"1", "true", "yes", "on"}
if LOCAL_PASSWORD_AUTH_ENABLED:
    raise RuntimeError("LOCAL_PASSWORD_AUTH_ENABLED must be false in production")

_authorization_middleware_index = MIDDLEWARE.index(
    "rentals.middleware.AuthorizationAgeMiddleware"
)
MIDDLEWARE.insert(
    _authorization_middleware_index + 1,
    "rentals.middleware.HealthCheckSessionRefresh",
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
