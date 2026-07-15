import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_email(subject: str, message: str, to: str, swallow_errors: bool = True) -> bool:
    """
    Send a single email.

    :param subject: email subject line.
    :param message: plain-text email body.
    :param to: recipient address.
    :param swallow_errors: if True (default - request/response call sites, e.g. password reset),
        SMTP failures are logged and swallowed so the caller can always respond 200 regardless of
        delivery success (no user-enumeration via error codes). If False (background task call
        sites, e.g. bookings/tasks.py), the exception is logged then re-raised so a Celery task can
        retry on transient SMTP/timeout errors instead of silently dropping the email.
    :return: True if the email was sent. Only returns False when swallow_errors is True; otherwise
        a failure raises instead of returning.
    """
    try:
        send_mail(subject=subject, message=message, from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[to])
        return True
    except Exception:
        logger.exception("Failed to send email (subject=%r) to %s.", subject, to)
        if swallow_errors:
            return False
        raise
