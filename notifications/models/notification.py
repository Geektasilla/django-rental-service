from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """A logged notification sent to a user (e.g. booking confirmation)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.TextField(_("message"))
    is_read = models.BooleanField(_("is read"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        :return: the recipient's email together with the notification message.
        """
        return f"{self.user.email}: {self.message}"
