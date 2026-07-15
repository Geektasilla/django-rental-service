from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from analytics.models import PropertyView, SearchHistory


class Command(BaseCommand):
    """
    Delete SearchHistory/PropertyView rows older than the retention window.

    GDPR Art. 5(1)(e) (storage limitation): analytics data has no legal retention requirement
    (unlike Booking/Ticket, which are kept for tax/dispute reasons - see users/services/
    anonymization.py), so it should not accumulate forever. Meant to run periodically (cron/Celery
    beat once one is configured) rather than manually, but works standalone either way.
    """

    help = "Delete SearchHistory/PropertyView rows older than ANALYTICS_RETENTION_DAYS."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Override settings.ANALYTICS_RETENTION_DAYS for this run.",
        )

    def handle(self, *args, **options) -> None:
        days = options["days"] if options["days"] is not None else settings.ANALYTICS_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)

        deleted_searches, _ = SearchHistory.objects.filter(created_at__lt=cutoff).delete()
        deleted_views, _ = PropertyView.objects.filter(viewed_at__lt=cutoff).delete()

        self.stdout.write(
            f"Deleted {deleted_searches} SearchHistory and {deleted_views} PropertyView row(s) "
            f"older than {days} days (before {cutoff.date()})."
        )
