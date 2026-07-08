from django.db import models
from django.utils.translation import gettext_lazy as _

from .address import Address
from .property import Property


class PropertyLocation(models.Model):
    """Unit-specific location details for a Property, linked to a shared Address."""

    property = models.OneToOneField(
        Property,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="location",
    )
    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name="property_locations",
    )
    apartment_number = models.CharField(_("apartment number"), max_length=20, blank=True)
    floor_info = models.CharField(
        _("floor info"),
        max_length=50,
        blank=True,
        help_text=_("e.g. '3. Stock Rechts'."),
    )

    class Meta:
        verbose_name = _("property location")
        verbose_name_plural = _("property locations")

    def __str__(self) -> str:
        """
        :return: the property title together with its address.
        """
        return f"{self.property.title} @ {self.address}"
