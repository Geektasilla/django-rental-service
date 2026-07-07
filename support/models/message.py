from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .ticket import Ticket


class Message(models.Model):
    """A single message in a support ticket's conversation thread."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_messages",
    )
    body = models.TextField(_("body"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("message")
        verbose_name_plural = _("messages")
        ordering = ["created_at"]

    def __str__(self) -> str:
        """
        :return: the sender's email together with the ticket's subject.
        """
        return f"{self.sender.email} on {self.ticket.subject}"
