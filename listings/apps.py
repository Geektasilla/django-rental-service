from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ListingsConfig(AppConfig):
    name = 'listings'
    verbose_name = _("Listings")

    def ready(self) -> None:
        """Connect the moderation signal handlers once the app registry is populated."""
        from . import signals  # noqa: F401
