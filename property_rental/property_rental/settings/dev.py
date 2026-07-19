"""Development settings — insecure, sqlite, debug on."""

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
SECRET_KEY = "django-insecure-dev-only-key-do-not-use-in-prod"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

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
