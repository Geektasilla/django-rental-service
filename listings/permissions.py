from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from listings.models import Property


class IsPropertyOwner(BasePermission):
    """Object-level permission: only the listing's own owner/agent (Property.owner) may act on it."""

    def has_object_permission(self, request: Request, view: APIView, obj: Property) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Property instance being accessed.
        :return: True if the requesting user is the listing's owner.
        """
        return obj.owner_id == request.user.id
