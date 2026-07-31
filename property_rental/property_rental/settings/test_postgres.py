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
if os.environ.get("DJANGO_SETTINGS_MODULE") == "property_rental.settings.test_postgres":
    DATABASES = {"default": postgres_database(required_env("DATABASE_URL"))}
