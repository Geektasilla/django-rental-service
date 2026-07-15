from django.db import models
from django.utils.translation import gettext_lazy as _


class BookingStatusChoices(models.TextChoices):
    """Lifecycle status of a Booking: PENDING -> BOOKED -> PAID, cancellable at any point before PAID settles."""

    PENDING = "pending", _("Pending owner approval")
    BOOKED = "booked", _("Booked")
    PAID = "paid", _("Paid")
    CANCELLED = "cancelled", _("Cancelled")
