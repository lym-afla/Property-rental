#!/usr/bin/env python3
"""Audit and smoke-test the production container image."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


def assert_runtime_contents(image: str) -> None:
    inspect = json.loads(docker("image", "inspect", image).stdout)[0]
    assert inspect["Config"]["User"] not in ("", "0", "root"), "image must run non-root"
    script = r'''
set -eu
for command in node npm uv gcc cc; do ! command -v "$command"; done
test ! -d /root/.cache
test ! -d /home/app/.cache
! find /app /opt/venv -type f \( -name '*.sqlite3' -o -name '*.map' -o -name '.env*' \) | grep .
! find /app -type d \( -name tests -o -name test -o -name e2e -o -name playwright -o -name __fixtures__ \) | grep .
! find /opt/venv -type d \( -name tests -o -name e2e -o -name playwright -o -name __fixtures__ \) | grep .
python - <<'PY'
import importlib.util
import os
from django.conf import settings
import django
django.setup()
assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql'
assert os.getuid() != 0
for module in (
    'cssbeautifier',
    'djlint',
    'editorconfig',
    'html_tag_names',
    'html_void_elements',
    'jsbeautifier',
    'json5',
    'pathspec',
):
    assert importlib.util.find_spec(module) is None, f'{module} must not be in runtime'
PY
'''
    env = [
        "DJANGO_SETTINGS_MODULE=property_rental.settings.prod",
        "DATABASE_URL=postgresql://audit:audit@127.0.0.1:9/audit",
        "DJANGO_SECRET_KEY=audit-only-key-with-enough-length-1234567890ABCDE",
        "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1",
        "DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost",
        "BUSINESS_TIME_ZONE=Europe/Moscow",
        "OIDC_ISSUER=https://auth.linik.ru/application/o/lifeos-rent/",
        "OIDC_CLIENT_ID=audit",
        "OIDC_CLIENT_SECRET=audit",
        "OIDC_CALLBACK_URL=https://rent.linik.ru/oidc/callback/",
        "OIDC_LOGOUT_URL=https://auth.linik.ru/application/o/lifeos-rent/end-session/",
        "OIDC_POST_LOGOUT_REDIRECT_URL=https://auth.linik.ru/",
    ]
    command = ["run", "--rm", "--entrypoint", "/bin/sh"]
    for value in env:
        command += ["-e", value]
    docker(*command, image, "-c", script)


def wait_for(url: str, timeout: float = 30) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(url, headers={"X-Forwarded-Proto": "https"})
            with urllib.request.urlopen(request, timeout=2) as response:
                assert response.status == 200
                return response.read()
        except Exception:
            time.sleep(0.25)
    raise AssertionError(f"timed out waiting for {url}")


def request_status(url: str, method: str) -> int:
    request = urllib.request.Request(
        url,
        data=b"" if method == "POST" else None,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Forwarded-Proto": "https",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def smoke_server(image: str) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host_port = sock.getsockname()[1]
    name = f"property-rental-audit-{host_port}"
    env = [
        "DATABASE_URL=postgresql://audit:audit@127.0.0.1:9/audit",
        "DJANGO_SECRET_KEY=audit-only-key-with-enough-length-1234567890ABCDE",
        "DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1",
        f"DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:{host_port}",
        "BUSINESS_TIME_ZONE=Europe/Moscow",
        "OIDC_ISSUER=https://auth.linik.ru/application/o/lifeos-rent/",
        "OIDC_CLIENT_ID=audit",
        "OIDC_CLIENT_SECRET=audit",
        "OIDC_CALLBACK_URL=https://rent.linik.ru/oidc/callback/",
        "OIDC_LOGOUT_URL=https://auth.linik.ru/application/o/lifeos-rent/end-session/",
        "OIDC_POST_LOGOUT_REDIRECT_URL=https://auth.linik.ru/",
    ]
    command = ["run", "-d", "--name", name, "-p", f"{host_port}:8000"]
    for value in env:
        command += ["-e", value]
    try:
        docker(*command, image)
        base = f"http://127.0.0.1:{host_port}"
        assert json.loads(wait_for(base + "/health/live")) == {"status": "ok"}
        spa = wait_for(base + "/")
        assert b"<html" in spa.lower()
        asset_path = spa.decode().split('src="/static/frontend/')[1].split('"')[0]
        assert wait_for(base + "/static/frontend/" + asset_path)
        backchannel_url = base + "/oidc/backchannel-logout/"
        assert request_status(backchannel_url, "POST") == 400
        assert request_status(backchannel_url, "GET") == 405
        docker("stop", "--time", "15", name)
        state = json.loads(docker("inspect", name).stdout)[0]["State"]
        assert state["ExitCode"] == 0, state
    finally:
        docker("rm", "-f", name, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    assert_runtime_contents(args.image)
    smoke_server(args.image)
    print(f"container audit passed: {args.image}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
