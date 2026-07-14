from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BookingsConfig(AppConfig):
    name = 'bookings'
    verbose_name = _("Bookings")

    def ready(self) -> None:
        """Connect the booking-notification signal handler once the app registry is populated."""
        from . import signals  # noqa: F401
