import logging

from django.db import connection
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Liveness/readiness probe for orchestration (Docker healthcheck, AWS ELB target group,
    Kubernetes probes). Intentionally minimal and AllowAny - it must be reachable without a token
    so infrastructure outside the app can poll it, and it must not do heavy work on every check.

    Verifies the database connection specifically (the one dependency whose failure should take
    the instance out of rotation) rather than just returning a static 200, which would report
    "healthy" even if the app can no longer serve any real request.
    """

    permission_classes = [AllowAny]

    @extend_schema(exclude=True)  # infrastructure probe, not part of the public API surface
    def get(self, request: Request) -> Response:
        """
        :param request: unused; no parameters.
        :return: 200 with {"status": "ok"} if the database is reachable, 503 otherwise.
        """
        try:
            connection.ensure_connection()
        except OperationalError:
            logger.exception("Health check failed: database unreachable.")
            return Response({"status": "unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "ok"})
