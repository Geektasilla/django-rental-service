from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from listings.models import Property


class PropertyView(models.Model):
    """A single view of a Property listing, logged for popularity ranking and guest analytics."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="views",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="property_views",
    )
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    viewed_at = models.DateTimeField(_("viewed at"), auto_now_add=True)

    class Meta:
        verbose_name = _("property view")
        verbose_name_plural = _("property views")
        ordering = ["-viewed_at"]

    def __str__(self) -> str:
        """
        :return: the viewed property's title together with the view timestamp.
        """
        return f"{self.property.title} @ {self.viewed_at}"
