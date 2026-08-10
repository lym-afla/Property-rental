"""Development settings — insecure, sqlite, debug on."""

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-prod"

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
OIDC_LOGOUT_TOKEN_MAX_AGE_SECONDS = 300
OIDC_POST_LOGOUT_REDIRECT_URL = "https://auth.linik.ru/"

# In dev, the SPA runs on Vite (:5173) which proxies to Django (:8000).
# CSRF_TRUSTED_ORIGINS must include both ports so Django accepts the
# X-CSRFToken header from the SPA's fetch calls through the proxy.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Keep request tests and local development warning-free before collectstatic has
# created STATIC_ROOT. Production settings intentionally keep WhiteNoise's
# manifest/static-root behaviour.
WHITENOISE_AUTOREFRESH = True

# Task 6: in dev, django-vite serves assets from the Vite dev server
# (:5173) and ignores the manifest. The dict is rebuilt here so
# ``dev_mode`` overrides the prod-mode default in base.py.
DJANGO_VITE = {
    "default": {
        "dev_mode": True,
        "dev_server_protocol": "http",
        "dev_server_host": "127.0.0.1",
        "dev_server_port": 5173,
        "manifest_path": str(BASE_DIR / "rentals" / "static" / "frontend" / "manifest.json"),
        "static_url_prefix": "frontend",
    },
}
