from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Ticket(models.Model):
    """A user-opened support ticket, optionally assigned to a support agent."""

    class StatusChoices(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In progress")
        CLOSED = "closed", _("Closed")

    # PROTECT, not CASCADE: deleting a user must not silently wipe support agents' message
    # history on tickets that user opened (Message.sender is also PROTECT).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        help_text=_("Support agent handling this ticket."),
    )
    subject = models.CharField(_("subject"), max_length=255)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.OPEN,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("ticket")
        verbose_name_plural = _("tickets")
        ordering = ["-created_at"]
        constraints = [
            # Hardcoded, not StatusChoices.values: nested TextChoices isn't visible from Meta.
            models.CheckConstraint(
                condition=models.Q(status__in=["open", "in_progress", "closed"]),
                name="ticket_status_valid",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the ticket's subject.
        """
        return self.subject
