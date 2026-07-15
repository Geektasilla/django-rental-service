from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    """Type of housing a Property represents, e.g. apartment, house, studio, room."""

    name = models.CharField(_("name"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")
        ordering = ["name"]

    def __str__(self) -> str:
        """
        :return: the category name.
        """
        return self.name
