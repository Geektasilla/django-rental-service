import logging

from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc: Exception, context: dict) -> Response:
    """
    Global DRF EXCEPTION_HANDLER.

    DRF's default handler already turns every APIException/Http404/PermissionDenied into a clean
    JSON response - this only adds a fallback for what it *doesn't* recognize (a bare Exception:
    an unexpected bug, a third-party library error, etc.), which DRF's default handler leaves
    unhandled (returns None) so it re-raises and Django renders it as an HTML 500 page with a full
    traceback - fine for a browser-rendered site, wrong for a JSON API, and a traceback leak to the
    client either way.

    :param exc: the raised exception.
    :param context: DRF's exception context (has 'view', 'request', etc.).
    :return: DRF's own response for recognized exceptions; a generic JSON 500 for everything else,
        with the full exception logged (not returned) for anything unrecognized.
    """
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    logger.exception("Unhandled exception in %s: %s", context.get("view"), exc)
    return Response({"detail": _("Internal server error.")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
