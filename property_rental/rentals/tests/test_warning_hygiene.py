import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHONPATH = str(PROJECT_ROOT / "property_rental")


def run_warning_check(code):
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "property_rental.settings.dev"
    env["PYTHONPATH"] = PYTHONPATH
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_staticfiles_storage_configuration_is_warning_free_for_django_42():
    result = run_warning_check(
        """
import warnings

from django.utils.deprecation import RemovedInDjango51Warning

warnings.simplefilter("error", RemovedInDjango51Warning)

import django
django.setup()

from django.contrib.staticfiles.storage import staticfiles_storage

assert (
    staticfiles_storage.__class__.__module__,
    staticfiles_storage.__class__.__name__,
) == (
    "whitenoise.storage",
    "CompressedManifestStaticFilesStorage",
)
"""
    )

    assert result.returncode == 0, result.stderr


def test_timezone_dependencies_import_without_datetime_deprecations():
    result = run_warning_check(
        """
import warnings

warnings.simplefilter("error", DeprecationWarning)

import dateutil.tz
import pytz
"""
    )

    assert result.returncode == 0, result.stderr


def test_development_wsgi_handler_initializes_without_static_root_warning():
    result = run_warning_check(
        """
import warnings

warnings.simplefilter("error", UserWarning)

import django
django.setup()

from django.core.handlers.wsgi import WSGIHandler
from django.test import override_settings

with override_settings(DEBUG=False):
    WSGIHandler()
"""
    )

    assert result.returncode == 0, result.stderr
