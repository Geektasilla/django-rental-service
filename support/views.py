from django.db.models import Count, Q, QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from common.utils import visible_to_participants
from support.models import Message, Ticket
from support.permissions import IsAssignedSupportAgent
from support.serializers import MessageSerializer, TicketSerializer
from users.models import User


class TicketViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Create/list/retrieve/update support tickets, plus a nested messages thread.

    No destroy: tickets are closed (status), never deleted.
    """

    serializer_class = TicketSerializer

    def get_permissions(self) -> list:
        """
        :return: instantiated permission objects for the current action - opening a ticket only
            requires being logged in; changing its status is restricted to the assigned agent.
        """
        if self.action in ("update", "partial_update"):
            permission_classes = [IsAuthenticated, IsAssignedSupportAgent]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self) -> QuerySet:
        """:return: tickets the user opened, is assigned to, or all of them for staff."""
        queryset = Ticket.objects.select_related("user", "assigned_to")
        return visible_to_participants(queryset, self.request.user, "user", "assigned_to")

    def perform_create(self, serializer: TicketSerializer) -> None:
        """
        Save the ticket as opened by the request user, then auto-assign it to whichever active
        support agent (is_support=True, is_active=True) currently has the fewest open tickets -
        no manual "claim" step, no assignment by a lead/superuser. Left unassigned if no support
        agent exists yet.
        """
        ticket = serializer.save(user=self.request.user)
        agent = (
            User.objects.filter(is_support=True, is_active=True)
            .annotate(
                open_ticket_count=Count(
                    "assigned_tickets",
                    filter=~Q(assigned_tickets__status=Ticket.StatusChoices.CLOSED),
                )
            )
            .order_by("open_ticket_count")
            .first()
        )
        if agent is not None:
            ticket.assigned_to = agent
            ticket.save(update_fields=["assigned_to"])

    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request: Request, pk: str | None = None) -> Response:
        """
        List this ticket's message thread (GET) or post a reply (POST). Visibility is already
        restricted to the ticket's opener/assigned agent/staff by get_queryset() - no extra
        participant check needed here.
        """
        ticket = self.get_object()
        if request.method == "POST":
            serializer = MessageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(ticket=ticket, sender=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        message_qs = ticket.messages.select_related("sender")
        serializer = MessageSerializer(message_qs, many=True)
        return Response(serializer.data)
