from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import TimeStampedModel
from listings.models import Property

from .status import BookingStatusChoices


class Booking(TimeStampedModel):
    """A tenant's reservation of a Property for a date range, daily or long-term."""

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=BookingStatusChoices.choices,
        default=BookingStatusChoices.PENDING,
        help_text=_("Set to BOOKED/CANCELLED only by the property's owner or agent approving or declining the request."),
    )
    price_frozen = models.DecimalField(
        _("price frozen"),
        max_digits=10,
        decimal_places=2,
        editable=False,
        help_text=_(
            "Copy of Property.price_per_day (DAILY) or Property.price_per_month (LONG_TERM) at "
            "booking creation time; later owner price changes don't affect this contract."
        ),
    )

    class Meta:
        verbose_name = _("booking")
        verbose_name_plural = _("bookings")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="booking_end_date_after_start_date",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the property title together with the booking's date range.
        """
        return f"{self.property.title} ({self.start_date} - {self.end_date})"

    def clean(self) -> None:
        """
        Enforce that end_date falls after start_date, then the DAILY-rental calendar rule:
        no two BOOKED/PAID bookings may overlap on the same property. PENDING requests don't
        block dates yet - multiple tenants may request the same range, and the owner picks one
        when approving it to BOOKED. LONG_TERM bookings rely on Property.is_active instead.

        :raises ValidationError: if end_date isn't after start_date, or if the requested date
            range overlaps an existing BOOKED/PAID booking for the same property.
        """
        if self.property_id is None or self.start_date is None or self.end_date is None:
            return
        if self.end_date <= self.start_date:
            raise ValidationError(_("End date must be after the start date."))
        if self.property.rent_type != Property.RentTypeChoices.DAILY:
            return

        conflicts = Booking.objects.filter(
            property_id=self.property_id,
            status__in=[BookingStatusChoices.BOOKED, BookingStatusChoices.PAID],
            start_date__lt=self.end_date,
            end_date__gt=self.start_date,
        ).exclude(pk=self.pk)
        if conflicts.exists():
            raise ValidationError(
                _("This property is already booked for the selected dates.")
            )

    def save(self, *args, **kwargs) -> None:
        """Freeze the rent_type-appropriate price from the linked Property on creation, then validate."""
        if self._state.adding:
            self.price_frozen = (
                self.property.price_per_day
                if self.property.rent_type == Property.RentTypeChoices.DAILY
                else self.property.price_per_month
            )
        self.full_clean()
        super().save(*args, **kwargs)
