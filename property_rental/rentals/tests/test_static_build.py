"""Static-build and production-container contracts."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "property_rental/rentals/static/frontend/manifest.json"


@contextmanager
def manifest_contents(contents: str | None):
    original = MANIFEST.read_bytes() if MANIFEST.exists() else None
    try:
        if contents is None:
            MANIFEST.unlink(missing_ok=True)
        else:
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(contents, encoding="utf-8")
        yield
    finally:
        if original is None:
            MANIFEST.unlink(missing_ok=True)
        else:
            MANIFEST.write_bytes(original)


def import_build_settings() -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = "property_rental.settings.build"
    for name in (
        "DATABASE_URL",
        "DJANGO_SECRET_KEY",
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
    ):
        environment.pop(name, None)
    return subprocess.run(
        [sys.executable, "-c", "from django.conf import settings; print(settings.DEBUG)"],
        cwd=ROOT / "property_rental",
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_build_settings_reject_missing_manifest():
    with manifest_contents(None):
        result = import_build_settings()
    assert result.returncode != 0
    assert "Vite manifest is required" in result.stderr


def test_build_settings_reject_invalid_manifest():
    with manifest_contents("not-json"):
        result = import_build_settings()
    assert result.returncode != 0
    assert "Vite manifest is invalid" in result.stderr


def test_build_settings_reject_manifest_without_application_entry():
    with manifest_contents(json.dumps({"index.html": {"file": "assets/index.js"}})):
        result = import_build_settings()
    assert result.returncode != 0
    assert "src/main.tsx" in result.stderr


def test_build_settings_accept_application_manifest_without_runtime_secrets():
    manifest = {"src/main.tsx": {"file": "assets/main-deadbeef.js", "isEntry": True}}
    with manifest_contents(json.dumps(manifest)):
        result = import_build_settings()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_production_build_disables_source_maps():
    config = (ROOT / "frontend/vite.config.ts").read_text(encoding="utf-8")
    assert "sourcemap: false" in config


def test_frontend_build_context_excludes_test_support_sources():
    """Docker's production frontend build must not compile test-only handlers."""
    tsconfig = (ROOT / "frontend/tsconfig.app.json").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert '"src/test"' in tsconfig
    assert '"src/__fixtures__"' in tsconfig
    assert '"src/**/*.test.*"' in tsconfig
    assert '"src/**/*.spec.*"' in tsconfig
    assert "frontend/src/test/" in dockerignore


def test_container_definition_exists_and_uses_non_root_runtime():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert "X-Forwarded-Proto" in dockerfile
    assert "find /app /opt/venv" in dockerfile
    assert "COPY --from=frontend-build /build/property_rental/rentals/static/frontend ./rentals/static/frontend" in dockerfile
    assert "property_rental.wsgi:application" in dockerfile
