"""Anonymous process and dependency health checks."""

from django.db import connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


def _response(status, status_code=200):
    return JsonResponse(
        {"status": status},
        status=status_code,
        json_dumps_params={"separators": (",", ":")},
    )


@never_cache
def liveness(request):
    """Report process liveness without touching the database or network."""
    return _response("ok")


@never_cache
def readiness(request):
    """Report whether the configured default database accepts a simple query."""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return _response("unavailable", status_code=503)
    return _response("ok")
