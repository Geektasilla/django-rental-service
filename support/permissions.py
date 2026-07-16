from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from support.models import Ticket


class IsAssignedSupportAgent(BasePermission):
    """Object-level permission: only the ticket's assigned support agent may change its status."""

    def has_object_permission(
        self, request: Request, view: APIView, obj: Ticket
    ) -> bool:
        """
        :param request: the incoming DRF request; ``request.user`` must be authenticated.
        :param view: the view being accessed.
        :param obj: the Ticket instance being updated.
        :return: True if the requesting user is this ticket's assigned agent.
        """
        return obj.assigned_to_id == request.user.id
