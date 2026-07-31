"""Session-auth endpoints for the SPA (Task 4).

Three plain DRF ``APIView`` classes mounted under ``/api/v1/auth/``:

* ``POST /api/v1/auth/login/``  — body ``{username, password}`` →
  ``200 {user: {...}}`` and sets the ``sessionid`` cookie, or
  ``400 {detail: "Invalid credentials"}`` on bad creds.
* ``POST /api/v1/auth/logout/`` — ``204`` and clears the session
  (requires an authenticated user).
* ``GET  /api/v1/auth/me/``     — ``200 {user: {...}}`` for the
  currently authenticated user, or ``401`` when anonymous.

These three views back the SPA's :class:`useAuth` hook (frontend Task 5).
The session-cookie semantics are Django's defaults — ``SESSION_COOKIE_*``
settings drive the same attributes the SPA fetch needs (``SameSite``,
``HttpOnly``, etc.).
"""

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from rentals.models import User
from .serializers import UserSerializer


class LocalPasswordAuthView:
    """Fail closed if a password endpoint is invoked outside development."""

    def dispatch(self, request, *args, **kwargs):
        if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class LoginView(LocalPasswordAuthView, APIView):
    """Log a user in via Django session auth.

    ``authentication_classes = []`` so an unauthenticated client can hit
    this endpoint to obtain a session; ``AllowAny`` mirrors that for the
    permission check. Successful auth calls ``login()`` to populate the
    request session and set the ``sessionid`` cookie on the response.
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # No auth needed to log in

    def post(self, request: Request) -> Response:
        username = request.data.get("username")
        password = request.data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """Log the current user out (clears the session)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Return the currently authenticated user's serialized shape."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(
            {"user": UserSerializer(request.user).data},
            status=status.HTTP_200_OK,
        )

    def patch(self, request: Request) -> Response:
        """Partially update the current user's settings.

        Accepts a partial payload of user fields (``default_currency``,
        ``chart_frequency``, ``chart_timeline``, ``digits``,
        ``use_default_currency_for_all_data``, etc.) and persists them.
        Returns the updated serialized user under the ``user`` key, the
        same shape as ``GET /me/``.
        """
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"user": serializer.data}, status=status.HTTP_200_OK)


class ChangePasswordView(LocalPasswordAuthView, APIView):
    """Change the current user's password (Task 8).

    Wraps Django's :class:`~django.contrib.auth.forms.PasswordChangeForm`
    so we get the standard validation (old password must match, new
    password fields must agree, new password must pass Django's password
    validators). Body shape ``{old_password, new_password1,
    new_password2}`` mirrors the form's field names verbatim so the form
    can be constructed from the request data directly.

    ``update_session_auth_hash`` keeps the user's current session valid
    after the password change (otherwise Django's auth model invalidates
    the session when the password hash rotates). This is what allows the
    SPA to keep working without a re-login after a successful change.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        form = PasswordChangeForm(
            request.user,
            data={
                "old_password": request.data.get("old_password", ""),
                "new_password1": request.data.get("new_password1", ""),
                "new_password2": request.data.get("new_password2", ""),
            },
        )
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, request.user)
            return Response(
                {"detail": "Password changed"}, status=status.HTTP_200_OK
            )
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(LocalPasswordAuthView, APIView):
    """Register a new user (Task 5).

    Accepts ``{username, password, email}`` and creates a new ``User``
    with ``is_landlord=True`` (the app's default — every registering
    user is a landlord; Phase 1's ``User.save()`` then auto-creates the
    matching ``Landlord`` row). On success the new user is logged in via
    ``login()`` so the response carries a ``sessionid`` cookie, matching
    the SPA's ``useAuth`` hook expectations.

    ``authentication_classes = []`` + ``AllowAny`` so an anonymous
    visitor can hit this endpoint. Validation errors are returned as
    field-keyed lists (``{"username": [...], "password": [...]}``) so
    the frontend can map them onto form fields.

    Reuses the same patterns as ``LoginView``: no auth on the request,
    manual field extraction, ``UserSerializer`` for the response shape.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

        errors: dict[str, list[str]] = {}

        if not username:
            errors.setdefault("username", []).append("This field is required.")
        elif User.objects.filter(username=username).exists():
            errors.setdefault("username", []).append("A user with this username already exists.")

        if not password:
            errors.setdefault("password", []).append("This field is required.")
        else:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                errors.setdefault("password", []).extend(e.messages)

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user = User(username=username, email=email, is_landlord=True)
        user.set_password(password)
        user.save()  # Phase 1: User.save() auto-creates a Landlord when is_landlord=True
        login(request, user)
        return Response({"user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)


class CsrfView(APIView):
    """Set the ``csrftoken`` cookie so the SPA can make authenticated mutations.

    Django's ``CsrfViewMiddleware`` only stamps the ``csrftoken`` cookie onto
    responses that render a template (i.e. the legacy server-rendered pages).
    The SPA consumes only JSON, so without this endpoint the browser never
    receives a ``csrftoken`` cookie and the first ``POST`` (e.g. logout) is
    rejected by CSRF with HTTP 403. The SPA's :class:`SessionProvider` calls
    this endpoint on boot — fire-and-forget; the response body is irrelevant,
    the ``Set-Cookie`` header is what matters.

    ``authentication_classes = []`` + ``AllowAny`` so the cookie is issued
    before the user has logged in (the cookie value is independent of the
    session). The ``@ensure_csrf_cookie`` decorator is what actually forces
    the middleware to set the cookie for a non-HTML response.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request: Request) -> Response:
        return Response({"detail": "CSRF cookie set"}, status=status.HTTP_200_OK)
