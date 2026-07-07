from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import TimeStampedModel

from .amenity import Amenity
from .category import Category


class Property(TimeStampedModel):
    """A rental listing, either daily (short-term) or long-term."""

    class RentTypeChoices(models.TextChoices):
        DAILY = "daily", _("Daily")
        LONG_TERM = "long_term", _("Long-term")

    class ModerationStatusChoices(models.TextChoices):
        PENDING = "pending", _("Pending review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"))
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="properties",
    )
    amenities = models.ManyToManyField(
        Amenity,
        related_name="properties",
        blank=True,
    )
    rent_type = models.CharField(
        _("rent type"),
        max_length=20,
        choices=RentTypeChoices.choices,
    )
    price_per_day = models.DecimalField(
        _("price per day"),
        max_digits=10,
        decimal_places=2,
    )
    rooms_count = models.PositiveSmallIntegerField(_("rooms count"))
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        help_text=_("Toggled by the owner to show/hide the listing from search results."),
    )

    moderation_status = models.CharField(
        _("moderation status"),
        max_length=20,
        choices=ModerationStatusChoices.choices,
        default=ModerationStatusChoices.PENDING,
        help_text=_("Result of automated + human review of this listing's text and photos."),
    )

    class Meta:
        verbose_name = _("property")
        verbose_name_plural = _("properties")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        :return: the listing's title.
        """
        return self.title
