from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from bookings.models import Booking
from listings.models import Property


class CanCancelBooking(BasePermission):
    """Object-level permission: either the booking's tenant or the listing's owner/agent may cancel it."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Booking
    ) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being cancelled.
        :return: True if the requesting user is the booking's tenant or the property's owner.
        """
        return (
            obj.tenant_id == request.user.id or obj.property.owner_id == request.user.id
        )


class IsBookingPropertyOwner(BasePermission):
    """Object-level permission: only the listing's owner/agent may confirm a pending booking on it."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Booking
    ) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being confirmed.
        :return: True if the requesting user owns the booking's Property.
        """
        return obj.property.owner_id == request.user.id


class OwnerIsVerifiedToConfirm(BasePermission):
    """
    Object-level permission: an owner-listed property's owner must be verified (OwnerProfile.
    is_verified) before they may confirm a booking on it - the point in the flow where the tenant
    is told "go ahead and pay", not the later "pay" stub (by then real money, sent outside the
    system, has already moved - blocking the confirm step is what actually prevents an unverified
    account from ever reaching that point). Agent-listed properties (listed_as=AGENT) are already
    gated at listing-creation time by AgentProfile.is_certified (Property.clean()) plus the
    agent_decertify_guard trigger, so they're exempt here.
    """

    message = _(
        "This listing's owner has not completed verification yet and cannot confirm bookings."
    )

    def has_object_permission(
        self, request: Request, view: APIView, obj: Booking
    ) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being confirmed.
        :return: True if the property is agent-listed (already gated elsewhere), or if it's
            owner-listed and the owner has a verified OwnerProfile.
        """
        property_obj = obj.property
        if property_obj.listed_as != Property.ListedAsChoices.OWNER:
            return True
        profile = getattr(property_obj.owner, "owner_profile", None)
        return bool(profile and profile.is_verified)


class IsBookingTenant(BasePermission):
    """Object-level permission: only the booking's own tenant may write a review for it."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Booking
    ) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being reviewed.
        :return: True if the requesting user is the booking's tenant.
        """
        return obj.tenant_id == request.user.id
