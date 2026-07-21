"""Production settings — reads all secrets from environment variables."""

import os

from .base import *  # noqa

DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # raises KeyError if missing — intentional
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DJANGO_DB_NAME"],
        "USER": os.environ["DJANGO_DB_USER"],
        "PASSWORD": os.environ["DJANGO_DB_PASSWORD"],
        "HOST": os.environ.get("DJANGO_DB_HOST", "localhost"),
        "PORT": os.environ.get("DJANGO_DB_PORT", "5432"),
    }
}

# Security settings (Phase 4 Task 5, 2026-07-19)
#
# All seven settings below are cookie/HSTS/redirect guards that the
# ``check --deploy`` command warns about (W004, W008, W012, W016). The
# session + CSRF cookies carry the user's auth, so they MUST be marked
# Secure (HTTPS-only) and SameSite=Lax (CSRF defense-in-depth against
# cross-site request inclusion). HSTS pins the HTTPS-only contract for
# one year (browsers refuse subsequent plain-HTTP requests for the
# domain and any subdomain), and SECURE_SSL_REDIRECT moves any stray
# HTTP request up to HTTPS before any view runs.
#
# CSRF_TRUSTED_ORIGINS is read from the env so the same code path works
# across deployments (e.g. ``app.example.com`` vs
# ``app.staging.example.net``) without a code change. Comma-separated,
# trailing empties filtered out — matches the ALLOWED_HOSTS pattern
# above. Django requires the scheme prefix (``https://``); operators
# must include it.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o
]
