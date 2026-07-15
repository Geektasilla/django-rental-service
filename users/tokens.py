from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from users.models import User


def encode_uid(user: User) -> str:
    """
    :param user: the account to encode a reference to.
    :return: urlsafe-base64-encoded pk, for embedding in reset/verification links.
    """
    return urlsafe_base64_encode(force_bytes(user.pk))


def decode_uid(uid: str) -> User | None:
    """
    :param uid: urlsafe-base64-encoded pk, as produced by ``encode_uid``.
    :return: the matching User, or None if the uid is malformed or matches no account.
    """
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None

# Django's built-in token generator is reused as-is for password reset; it already invalidates
# itself once the password changes, so no separate token model is needed.
password_reset_token_generator = PasswordResetTokenGenerator()


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Separate token generator for email verification - deliberately not the same instance as
    ``password_reset_token_generator``, since the two flows should not be able to replay each
    other's tokens even though the underlying algorithm is identical.
    """

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        """
        :param user: the account the token is for.
        :param timestamp: token creation time, injected by the base class.
        :return: a string that changes once the token is consumed (``is_email_verified`` flips to
            True) or the target email changes, so a used/stale token can't be replayed.
        """
        return f"{user.pk}{timestamp}{user.is_email_verified}{user.email}"


email_verification_token_generator = EmailVerificationTokenGenerator()


def revoke_all_sessions(user: User) -> None:
    """
    Blacklist every outstanding refresh token for this user.

    Without this, a refresh token issued before a password reset/change/account anonymization
    (e.g. one leaked to an attacker) would keep minting new access tokens indefinitely - changing
    the password (or locking the account) alone doesn't invalidate already-issued JWTs.

    :param user: the account whose sessions are being revoked.
    """
    outstanding = OutstandingToken.objects.filter(user=user)
    BlacklistedToken.objects.bulk_create(
        (BlacklistedToken(token=token) for token in outstanding.exclude(blacklistedtoken__isnull=False)),
        ignore_conflicts=True,
    )


def set_password_and_revoke_sessions(user: User, new_password: str) -> None:
    """
    Set a new password and revoke every outstanding refresh token for this user.

    :param user: the account whose password is being changed.
    :param new_password: the new, already-validated plaintext password.
    """
    user.set_password(new_password)
    user.save()
    revoke_all_sessions(user)
