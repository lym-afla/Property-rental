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

from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


class LoginView(APIView):
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
