from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from bookings.models import Booking


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
