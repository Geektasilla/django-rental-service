from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from common.models import ProfileStatusChoices


def _profile_is_active(user, related_name: str) -> bool:
    """
    Check whether a user's role profile exists and is in ACTIVE status.

    :param user: the authenticated User instance.
    :param related_name: the one-to-one reverse accessor name (e.g. "owner_profile").
    :return: True if the profile exists and its status is ACTIVE, False otherwise.
    """
    profile = getattr(user, related_name, None)
    return profile is not None and profile.status == ProfileStatusChoices.ACTIVE


class IsOwnerOrAgent(BasePermission):
    """Grants access to users with an active owner or agent profile."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :return: True if the user has an ACTIVE OwnerProfile or an ACTIVE AgentProfile.
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return (user.is_owner and _profile_is_active(user, "owner_profile")) or (
            user.is_agent and _profile_is_active(user, "agent_profile")
        )


class IsTenant(BasePermission):
    """Grants access to users with an active tenant profile."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :return: True if the user has an ACTIVE TenantProfile.
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return _profile_is_active(user, "tenant_profile")


class IsSupportAgent(BasePermission):
    """Grants access to active support agents (no dedicated role profile exists for this role)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :return: True if the user has is_support=True and is not deactivated (is_active).
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_support and user.is_active)


class IsModerator(BasePermission):
    """Grants access to active moderators (no dedicated role profile exists for this role)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :return: True if the user has is_moderator=True and is not deactivated (is_active).
        """
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_moderator and user.is_active)
