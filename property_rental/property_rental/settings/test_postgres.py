"""PostgreSQL-backed settings for integration environments."""

from .base import *  # noqa
from .env import postgres_database, required_env


SECRET_KEY = "test-postgres-only-key"
DEBUG = False
DATABASES = {"default": postgres_database(required_env("DATABASE_URL"))}
