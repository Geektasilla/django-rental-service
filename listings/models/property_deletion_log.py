from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PropertyDeletionLog(models.Model):
    """
    Audit trail entry for a hard-deleted Property.

    Not a ForeignKey to Property - the row it describes is gone by the time this is written, so
    the identifying fields are a denormalized snapshot instead (id/title at time of deletion).
    """

    property_id = models.PositiveIntegerField(_("property id"))
    property_title = models.CharField(_("property title"), max_length=255)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="property_deletions",
        help_text=_(
            "The listing's owner - only the owner may delete their own listing."
        ),
    )
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    deleted_at = models.DateTimeField(_("deleted at"), auto_now_add=True)

    class Meta:
        verbose_name = _("property deletion log")
        verbose_name_plural = _("property deletion logs")
        ordering = ["-deleted_at"]

    def __str__(self) -> str:
        """
        :return: the deleted property's title together with its former id.
        """
        return f"{self.property_title} (id={self.property_id})"
