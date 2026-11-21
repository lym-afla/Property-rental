"""PostgreSQL-backed settings for integration environments.

The filename is intentionally compatible with the existing CI contract
(``property_rental.settings.test_postgres``), but pytest's default
``test_*.py`` collection pattern can import this module while running the
ordinary SQLite-backed local suite. Only require ``DATABASE_URL`` when this
settings module is actively selected.
"""

import os

from .base import *  # noqa
from .env import postgres_database, required_env


SECRET_KEY = "test-postgres-only-key"
DEBUG = False
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"
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
if os.environ.get("DJANGO_SETTINGS_MODULE") == "property_rental.settings.test_postgres":
    DATABASES = {"default": postgres_database(required_env("DATABASE_URL"))}
