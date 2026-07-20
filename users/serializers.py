from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from common.validators import no_html_tags_validator
from users.models import User
from users.models.agent import AgentProfile
from users.models.owner import OwnerProfile
from users.models.tenant import TenantProfile
from users.tokens import (
    decode_uid,
    email_verification_token_generator,
    password_reset_token_generator,
)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Public self-registration serializer.

    Deliberately excludes ``is_support``/``is_moderator``, ``is_staff``, ``is_superuser`` and
    ``is_active``.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        label=_("password"),
        style={"input_type": "password"},
    )

    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
        validators=[no_html_tags_validator],
    )
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
        validators=[no_html_tags_validator],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "password",
            "phone",
            "first_name",
            "last_name",
            "gender",
            "is_owner",
            "is_agent",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data: dict) -> User:
        """
        :param validated_data: fields validated against ``Meta.fields``.
        :return: the newly created, password-hashed User.
        """
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LogoutSerializer(serializers.Serializer):
    """Input for the logout endpoint: the refresh token to blacklist."""

    refresh = serializers.CharField(write_only=True, label=_("refresh token"))


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and updating the authenticated user's profile.
    """

    first_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
        validators=[no_html_tags_validator],
    )
    last_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True,
        validators=[no_html_tags_validator],
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "is_owner",
            "is_agent",
            "is_support",
            "is_moderator",
            "is_email_verified",
        ]
        read_only_fields = [
            "id",
            "email",  # Email changes should be handled separately for verification
            "is_owner",
            "is_agent",
            "is_support",
            "is_moderator",
            "is_email_verified",
        ]

    def validate(self, attrs: dict) -> dict:
        """
        :param attrs: validated field values.
        :return: attrs, unchanged.
        :raises serializers.ValidationError: if the request body attempts to set a read-only
            field, or ``is_staff``/``is_superuser`` (not exposed in ``Meta.fields`` at all, but
            silently dropped by DRF otherwise instead of surfacing the attempt to the caller).
        """
        restricted = [
            field
            for field in (*self.Meta.read_only_fields, "is_staff", "is_superuser")
            if field in self.initial_data
        ]
        if restricted:
            raise serializers.ValidationError(
                {
                    "detail": _("Cannot set restricted field(s): %(fields)s.")
                    % {"fields": ", ".join(restricted)}
                }
            )
        return attrs


class OwnerProfileSerializer(serializers.ModelSerializer):
    """
    Self-service create/view/update of the caller's own OwnerProfile.

    ``is_verified``/``verified_at`` are deliberately read-only - a user can submit
    ``verification_document`` (claim proof), but only a moderator can flip verification (see
    VerifyOwnerProfileView), the same "user proposes, moderator confirms" split already used for
    Property.moderation_status. ``status`` is also read-only here for now - self-disabling a role
    is a related but separate feature, not implemented by this endpoint.
    """

    class Meta:
        model = OwnerProfile
        fields = [
            "tax_id",
            "bio",
            "is_company",
            "company_name",
            "registration_number",
            "languages",
            "verification_document",
            "is_verified",
            "verified_at",
            "status",
        ]
        read_only_fields = ["is_verified", "verified_at", "status"]


class AgentProfileSerializer(serializers.ModelSerializer):
    """
    Self-service create/view/update of the caller's own AgentProfile.

    ``is_certified`` is read-only - only a moderator can certify an agent (see
    CertifyAgentProfileView); Property.clean() requires is_certified=True before a listing can be
    created with listed_as=agent, so an unverified claim here grants no extra access on its own.
    """

    class Meta:
        model = AgentProfile
        fields = [
            "company_name",
            "license_number",
            "website",
            "bio",
            "is_certified",
            "status",
        ]
        read_only_fields = ["is_certified", "status"]


class TenantProfileSerializer(serializers.ModelSerializer):
    """Self-service create/view/update of the caller's own TenantProfile."""

    class Meta:
        model = TenantProfile
        fields = ["passport_data", "status"]
        read_only_fields = ["status"]


class PasswordResetRequestSerializer(serializers.Serializer):
    """Input for requesting a password-reset email."""

    email = serializers.EmailField(label=_("email"))


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Input for completing a password reset: the uid+token from the emailed link, plus the new
    password.
    """

    uid = serializers.CharField(label=_("uid"))
    token = serializers.CharField(label=_("token"))
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        label=_("new password"),
        style={"input_type": "password"},
    )

    def validate(self, attrs: dict) -> dict:
        """
        :param attrs: raw ``uid``/``token``/``new_password``.
        :raises serializers.ValidationError: if the uid doesn't decode to an existing user, or the
            token is invalid/expired/already used.
        :return: attrs with a resolved ``user`` key added.
        """
        return _validate_uid_token(
            attrs,
            password_reset_token_generator,
            invalid_msg=_("Invalid reset link."),
            expired_msg=_("Invalid or expired reset link."),
        )


def _validate_uid_token(
    attrs: dict, token_generator, invalid_msg: str, expired_msg: str
) -> dict:
    """
    Shared body for "resolve a user from an emailed uid+token link" validators.

    :param attrs: raw ``uid``/``token`` input.
    :param token_generator: the generator whose ``check_token(user, token)`` validates the link.
    :param invalid_msg: error to raise if the uid doesn't decode to an existing user.
    :param expired_msg: error to raise if the token is invalid/expired/already used.
    :raises serializers.ValidationError: per ``invalid_msg``/``expired_msg`` above.
    :return: attrs with a resolved ``user`` key added.
    """
    user = decode_uid(attrs["uid"])
    if user is None:
        raise serializers.ValidationError(invalid_msg)

    if not token_generator.check_token(user, attrs["token"]):
        raise serializers.ValidationError(expired_msg)

    attrs["user"] = user
    return attrs


def _validate_matches_request_user_password(
    serializer: serializers.Serializer, value: str, error: str
) -> str:
    """
    Shared field-validator body for "confirm your current password" fields.

    :param serializer: the serializer instance being validated (needs ``context["request"]``).
    :param value: the password supplied by the caller.
    :param error: message to raise if it doesn't match.
    :raises serializers.ValidationError: if ``value`` doesn't match the authenticated user's password.
    :return: the same value, unchanged.
    """
    user = serializer.context["request"].user
    if not user.check_password(value):
        raise serializers.ValidationError(error)
    return value


class ChangePasswordSerializer(serializers.Serializer):
    """Input for changing the authenticated user's own password."""

    current_password = serializers.CharField(
        write_only=True, label=_("current password"), style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        label=_("new password"),
        style={"input_type": "password"},
    )

    def validate_current_password(self, value: str) -> str:
        """
        :param value: the password supplied by the caller.
        :raises serializers.ValidationError: if it doesn't match the authenticated user's password.
        :return: the same value, unchanged.
        """
        return _validate_matches_request_user_password(
            self, value, _("Current password is incorrect.")
        )


class AccountDeletionSerializer(serializers.Serializer):
    """Input for the GDPR account-deletion (anonymization) endpoint: password confirmation only."""

    password = serializers.CharField(write_only=True, label=_("password"))

    def validate_password(self, value: str) -> str:
        """
        :param value: the password supplied by the caller.
        :raises serializers.ValidationError: if it doesn't match the authenticated user's password.
        :return: the same value, unchanged.
        """
        return _validate_matches_request_user_password(
            self, value, _("Password is incorrect.")
        )


class EmailVerificationRequestSerializer(serializers.Serializer):
    """Empty input - the target user is the authenticated caller, not a request field."""


class EmailVerificationConfirmSerializer(serializers.Serializer):
    """Input for confirming an email address: the uid+token from the emailed link."""

    uid = serializers.CharField(label=_("uid"))
    token = serializers.CharField(label=_("token"))

    def validate(self, attrs: dict) -> dict:
        """
        :param attrs: raw ``uid``/``token``.
        :raises serializers.ValidationError: if the uid doesn't decode to an existing user, or the
            token is invalid/expired/already used.
        :return: attrs with a resolved ``user`` key added.
        """
        return _validate_uid_token(
            attrs,
            email_verification_token_generator,
            invalid_msg=_("Invalid verification link."),
            expired_msg=_("Invalid or expired verification link."),
        )
