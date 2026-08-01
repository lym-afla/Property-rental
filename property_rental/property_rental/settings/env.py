"""Strict environment parsing shared by non-development settings modules."""

import os
from urllib.parse import unquote, urlparse


def required_env(name: str) -> str:
    """Return a required, non-blank environment variable."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


def csv_env(name: str) -> list[str]:
    """Return non-empty, whitespace-trimmed values from a CSV environment variable."""
    return [value.strip() for value in required_env(name).split(",") if value.strip()]


def optional_https_url_env(name: str, *, allowed_origins: set[str]) -> str | None:
    """Return an optional HTTPS URL whose origin is explicitly approved."""
    value = os.environ.get(name, "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme != "https" or origin not in allowed_origins:
        allowed = ", ".join(sorted(allowed_origins))
        raise RuntimeError(f"{name} must use one of these HTTPS origins: {allowed}")
    if parsed.username or parsed.password:
        raise RuntimeError(f"{name} must not include URL credentials")
    return value


def postgres_database(url: str) -> dict[str, object]:
    """Translate a PostgreSQL URL into Django's database connection settings."""
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use a PostgreSQL URL")
    if not parsed.path or parsed.path == "/":
        raise ValueError("DATABASE_URL must include a database name")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_HEALTH_CHECKS": True,
    }
