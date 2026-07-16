from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from bookings.models import Booking, BookingStatusChoices

REVIEW_WINDOW_DAYS = 90


class Review(models.Model):
    """A tenant's rating and comment for a completed (PAID) booking."""

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="review",
    )
    rating = models.PositiveSmallIntegerField(
        _("rating"),
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(_("comment"))
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("review")
        verbose_name_plural = _("reviews")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name="review_rating_range",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the rating together with the reviewed property's title.
        """
        return f"{self.rating}/5 for {self.booking.property.title}"

    def clean(self) -> None:
        """
        Enforce that a review only ever attaches to a settled booking, within a bounded window
        after the stay ended. Who is allowed to write it (must be the booking's own tenant) is a
        request-level concern, not a data invariant, so it's checked in the view/permission layer
        instead (bookings/permissions.py::IsBookingTenant), not here.

        :raises ValidationError: if the booking isn't PAID, or REVIEW_WINDOW_DAYS have passed
            since the booking's end_date.
        """
        if self.booking_id is None:
            return
        if self.booking.status != BookingStatusChoices.PAID:
            raise ValidationError(_("A review can only be left for a paid booking."))
        deadline = self.booking.end_date + timedelta(days=REVIEW_WINDOW_DAYS)
        if timezone.now().date() > deadline:
            raise ValidationError(
                _(
                    "Reviews must be submitted within %(days)d days of the booking's end date."
                )
                % {"days": REVIEW_WINDOW_DAYS}
            )

    def save(self, *args, **kwargs) -> None:
        """Run full model validation (including the PAID/time-window rules) before every save."""
        self.full_clean()
        super().save(*args, **kwargs)
