from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from users.models import User


class RegisterSerializer(serializers.ModelSerializer):
    """
    Public self-registration serializer.

    Deliberately excludes ``is_support``/``is_moderator``, ``is_staff``, ``is_superuser`` and
    ``is_active``.
    """

    password = serializers.CharField(write_only=True, validators=[validate_password], label=_("password"))

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
        ]
        read_only_fields = [
            "id",
            "email", # Email changes should be handled separately for verification
            "is_owner",
            "is_agent",
            "is_support",
            "is_moderator",
        ]
