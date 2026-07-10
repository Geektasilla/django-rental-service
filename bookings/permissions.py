from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from bookings.models import Booking


class CanCancelBooking(BasePermission):
    """Object-level permission: either the booking's tenant or the listing's owner/agent may cancel it."""

    def has_object_permission(self, request: Request, view: APIView, obj: Booking) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being cancelled.
        :return: True if the requesting user is the booking's tenant or the property's owner.
        """
        return obj.tenant_id == request.user.id or obj.property.owner_id == request.user.id


class IsBookingPropertyOwner(BasePermission):
    """Object-level permission: only the listing's owner/agent may confirm a pending booking on it."""

    def has_object_permission(self, request: Request, view: APIView, obj: Booking) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being confirmed.
        :return: True if the requesting user owns the booking's Property.
        """
        return obj.property.owner_id == request.user.id


class IsBookingTenant(BasePermission):
    """Object-level permission: only the booking's own tenant may write a review for it."""

    def has_object_permission(self, request: Request, view: APIView, obj: Booking) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Booking instance being reviewed.
        :return: True if the requesting user is the booking's tenant.
        """
        return obj.tenant_id == request.user.id
