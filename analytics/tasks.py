from celery import shared_task
from django.core.management import call_command


@shared_task
def cleanup_analytics_task() -> None:
    """Periodic counterpart of ``manage.py cleanup_analytics`` - see CELERY_BEAT_SCHEDULE."""
    call_command("cleanup_analytics")
