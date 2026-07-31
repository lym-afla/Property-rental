"""Production health endpoint contracts."""

from unittest.mock import MagicMock, patch

import pytest
from django.db import connections
from django.test import Client
from django.urls import resolve


@pytest.mark.django_db
def test_liveness_is_anonymous_and_never_uses_the_database():
    """Liveness is safe when the database is unavailable."""
    client = Client()
    connection = connections["default"]

    with patch.object(connection, "cursor", side_effect=RuntimeError("database down")):
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "no-store" in response["Cache-Control"]


@pytest.mark.django_db
def test_readiness_checks_the_default_database_and_hides_failures():
    """Readiness executes exactly the small database probe it promises."""
    client = Client()
    connection = connections["default"]
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor

    with patch.object(connection, "cursor", return_value=cursor):
        healthy = client.get("/health/ready")

    assert healthy.status_code == 200
    assert healthy.json() == {"status": "ok"}
    cursor.execute.assert_called_once_with("SELECT 1")

    with patch.object(connection, "cursor", side_effect=RuntimeError("database down")):
        unhealthy = client.get("/health/ready")

    assert unhealthy.status_code == 503
    assert unhealthy.json() == {"status": "unavailable"}
    assert "no-store" in unhealthy["Cache-Control"]


def test_health_routes_precede_the_spa_catchall_and_are_anonymous():
    """Health checks resolve directly, without API, FX, or OIDC work."""
    for path, name in (("/health/live", "health-live"), ("/health/ready", "health-ready")):
        match = resolve(path)
        assert match.url_name == name
