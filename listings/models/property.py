from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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

    class ListedAsChoices(models.TextChoices):
        OWNER = "owner", _("As owner (own property)")
        AGENT = "agent", _("As agent (on behalf of a client)")

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
        _("price per day (EUR)"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=_("Required for DAILY listings. Price in EUR - this platform only serves the German market."),
    )
    price_per_month = models.DecimalField(
        _("price per month (EUR)"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=_(
            "Required for LONG_TERM listings (German long-term rent is always quoted monthly, "
            "e.g. Kaltmiete). Price in EUR."
        ),
    )
    rooms_count = models.PositiveSmallIntegerField(
        _("rooms count"),
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )
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

    listed_as = models.CharField(
        _("listed as"),
        max_length=20,
        choices=ListedAsChoices.choices,
        default=ListedAsChoices.OWNER,
        help_text=_("Whether the owner is listing their own property, or an agent acting on a client's behalf."),
    )
    power_of_attorney_document = models.FileField(
        _("power of attorney document"),
        upload_to="listings/power_of_attorney/",
        null=True,
        blank=True,
        help_text=_("Required when listed_as=AGENT; proves authorization to list this specific property."),
    )

    class Meta:
        verbose_name = _("property")
        verbose_name_plural = _("properties")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price_per_day__isnull=True) | models.Q(price_per_day__gt=0),
                name="property_price_per_day_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(price_per_month__isnull=True) | models.Q(price_per_month__gt=0),
                name="property_price_per_month_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(rooms_count__gte=1) & models.Q(rooms_count__lte=20),
                name="property_rooms_count_range",
            ),
            # Values hardcoded, not RentTypeChoices.values: a nested TextChoices class isn't
            # visible from a sibling nested Meta class (Python class-body scoping rules).
            models.CheckConstraint(
                condition=models.Q(rent_type__in=["daily", "long_term"]),
                name="property_rent_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(moderation_status__in=["pending", "approved", "rejected"]),
                name="property_moderation_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(listed_as__in=["owner", "agent"]),
                name="property_listed_as_valid",
            ),
            # Same-row rules from Property.clean(), now also enforced at the DB level so
            # bulk_create()/bulk_update()/.update() can't bypass them.
            models.CheckConstraint(
                condition=(
                    models.Q(rent_type="daily", price_per_day__isnull=False)
                    | models.Q(rent_type="long_term", price_per_month__isnull=False)
                ),
                name="property_price_required_for_rent_type",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(listed_as="owner")
                    | (
                        models.Q(listed_as="agent")
                        & models.Q(power_of_attorney_document__isnull=False)
                        & ~models.Q(power_of_attorney_document="")
                    )
                ),
                name="property_poa_required_for_agent",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the listing's title.
        """
        return self.title

    def clean(self) -> None:
        """
        Enforce who may list a property in which capacity:
        - listed_as=OWNER requires the owner to actually have owner status.
        - listed_as=AGENT requires a per-listing power of attorney document, plus the owner
          being a certified agent (a listing always states which capacity it's listed under -
          a user who is both owner and agent must pick one explicitly per listing).

        Also enforces that the price field matching rent_type is set: price_per_day for DAILY,
        price_per_month for LONG_TERM (German long-term rent is quoted monthly, not daily).

        :raises ValidationError: if the capacity requirements above aren't met, or if the price
            field matching rent_type is missing.
        """
        if self.rent_type == self.RentTypeChoices.DAILY and self.price_per_day is None:
            raise ValidationError(_("price_per_day is required for DAILY listings."))
        if self.rent_type == self.RentTypeChoices.LONG_TERM and self.price_per_month is None:
            raise ValidationError(_("price_per_month is required for LONG_TERM listings."))

        if self.owner_id is None:
            return

        if self.listed_as == self.ListedAsChoices.AGENT:
            if not self.power_of_attorney_document:
                raise ValidationError(
                    _("A power of attorney document is required when listing as an agent.")
                )
            agent_profile = getattr(self.owner, "agent_profile", None)
            if not (self.owner.is_agent and agent_profile and agent_profile.is_certified):
                raise ValidationError(
                    _("Only a certified agent may list a property on a client's behalf.")
                )
        else:
            if not self.owner.is_owner:
                raise ValidationError(
                    _("Only a user with owner status may list a property as themselves.")
                )

    def save(self, *args, **kwargs) -> None:
        """Validate the listing capacity (listed_as) before delegating to the parent save."""
        self.full_clean()
        super().save(*args, **kwargs)
