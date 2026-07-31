"""Strict production settings, with all runtime configuration from the environment."""

from .base import *  # noqa
from .env import csv_env, postgres_database, required_env


DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
TIME_ZONE = required_env("BUSINESS_TIME_ZONE")
DATABASES = {"default": postgres_database(required_env("DATABASE_URL"))}

INSTALLED_APPS += ["mozilla_django_oidc"]
AUTHENTICATION_BACKENDS = [
    "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]
OIDC_ISSUER = required_env("OIDC_ISSUER").rstrip("/")
OIDC_RP_CLIENT_ID = required_env("OIDC_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = required_env("OIDC_CLIENT_SECRET")
OIDC_CALLBACK_URL = required_env("OIDC_CALLBACK_URL")
OIDC_LOGOUT_URL = required_env("OIDC_LOGOUT_URL")
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{OIDC_ISSUER}/authorize/"
OIDC_OP_TOKEN_ENDPOINT = f"{OIDC_ISSUER}/token/"
OIDC_OP_USER_ENDPOINT = f"{OIDC_ISSUER}/userinfo/"
OIDC_OP_JWKS_ENDPOINT = f"{OIDC_ISSUER}/jwks/"
OIDC_USE_PKCE = True
OIDC_PKCE_CODE_CHALLENGE_METHOD = "S256"

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
