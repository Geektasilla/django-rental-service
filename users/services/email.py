from django.conf import settings
from django.utils.translation import gettext_lazy as _

from common.services.email import send_email
from users.models import User


def send_password_reset_email(user: User, uid: str, token: str) -> bool:
    """
    :param user: the account the reset link is for.
    :param uid: urlsafe-base64-encoded user pk (django.utils.http.urlsafe_base64_encode).
    :param token: password_reset_token_generator token for this user.
    :return: True if the email was sent, False if sending failed.
    """
    reset_link = f"{settings.FRONTEND_URL}/password-reset/confirm?uid={uid}&token={token}"
    return send_email(
        subject=str(_("Reset your password")),
        message=str(_("Use this link to reset your password: %(link)s") % {"link": reset_link}),
        to=user.email,
    )


def send_email_verification_email(user: User, uid: str, token: str) -> bool:
    """
    :param user: the account whose email is being verified.
    :param uid: urlsafe-base64-encoded user pk (django.utils.http.urlsafe_base64_encode).
    :param token: email_verification_token_generator token for this user.
    :return: True if the email was sent, False if sending failed.
    """
    verify_link = f"{settings.FRONTEND_URL}/email-verification/confirm?uid={uid}&token={token}"
    return send_email(
        subject=str(_("Verify your email address")),
        message=str(_("Use this link to verify your email: %(link)s") % {"link": verify_link}),
        to=user.email,
    )
