from django.apps import AppConfig


class ListingsConfig(AppConfig):
    name = 'listings'

    def ready(self) -> None:
        """Connect the moderation signal handlers once the app registry is populated."""
        from . import signals  # noqa: F401
