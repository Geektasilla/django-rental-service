from django.db import models
from django.utils.translation import gettext_lazy as _


class Amenity(models.Model):
    """A feature a property can offer, e.g. Wi-Fi, parking, washer."""

    name = models.CharField(_("name"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("amenity")
        verbose_name_plural = _("amenities")
        ordering = ["name"]

    def __str__(self) -> str:
        """
        :return: the amenity name.
        """
        return self.name
