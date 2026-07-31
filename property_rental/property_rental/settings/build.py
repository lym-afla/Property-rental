"""Settings used only while building static assets in a container image."""

import json

from .base import *  # noqa


# Django requires a key while importing settings. This value is build-only and
# is never emitted into the generated static files or runtime environment.
SECRET_KEY = "build-only-not-a-runtime-secret"
DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

_manifest_path = VITE_MANIFEST_PATH
if not _manifest_path.is_file():
    raise RuntimeError(f"Vite manifest is required before collectstatic: {_manifest_path}")

try:
    _manifest = json.loads(_manifest_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as error:
    raise RuntimeError(f"Vite manifest is invalid: {_manifest_path}") from error

if "src/main.tsx" not in _manifest:
    raise RuntimeError("Vite manifest must contain the src/main.tsx entry")
