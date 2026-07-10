from django.db import models
from django.utils.translation import gettext_lazy as _

from .postal_code import PostalCode


class Address(models.Model):
    """Unique building entry (3NF): postal_code + street + house_number identify one building."""

    postal_code = models.ForeignKey(
        PostalCode,
        on_delete=models.PROTECT,
        related_name="addresses",
    )
    street = models.CharField(_("street"), max_length=255)
    house_number = models.CharField(_("house number"), max_length=20)

    class Meta:
        verbose_name = _("address")
        verbose_name_plural = _("addresses")
        constraints = [
            models.UniqueConstraint(
                fields=["postal_code", "street", "house_number"],
                name="unique_address_per_building",
            )
        ]

    def __str__(self) -> str:
        """
        :return: the full street address including postal code and city.
        """
        return f"{self.street} {self.house_number}, {self.postal_code_id} {self.postal_code.city}"
