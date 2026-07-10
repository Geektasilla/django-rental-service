from django.db.models import QuerySet
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from notifications.models import Notification
from notifications.serializers import NotificationSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    List/retrieve a user's own notifications and mark them read.

    No create/destroy: notifications are only ever written by the system (a signal that creates
    them on relevant events isn't wired up yet), and there's no read-only-log-entry deletion.
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet:
        """:return: the current user's own notifications only - never another user's."""
        return Notification.objects.filter(user=self.request.user)
