from django.db import models
from django.utils.translation import gettext_lazy as _


class PostalCode(models.Model):
    """German postal code lookup table (3NF): code maps to city/state."""

    code = models.CharField(_("postal code"), max_length=10, primary_key=True)
    # Indexed: PropertyFilter's `city` filter (listings/filters.py) joins Property -> Location ->
    # Address -> PostalCode and filters on this field on every such search request.
    city = models.CharField(_("city"), max_length=100, db_index=True)
    state = models.CharField(
        _("state"),
        max_length=100,
        help_text=_("German federal state (Bundesland), e.g. Berlin, Bayern."),
    )

    class Meta:
        verbose_name = _("postal code")
        verbose_name_plural = _("postal codes")
        ordering = ["code"]

    def __str__(self) -> str:
        """
        :return: the postal code together with its city.
        """
        return f"{self.code} {self.city}"
