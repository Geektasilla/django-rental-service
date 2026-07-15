import logging

from celery import shared_task

from bookings.models import Booking
from bookings.services.email import send_new_booking_request_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_new_booking_request_email_task(self, booking_id: int) -> None:
    """
    Async counterpart of the in-app Notification created synchronously in bookings/signals.py.

    Runs off the request-response cycle so an SMTP hiccup can't slow down booking creation. Retries
    up to 3 times (60s apart) on any send failure - a booking already exists in the DB by the time
    this runs, so a lost email (rather than a lost booking) is the only failure mode to guard
    against here.

    :param booking_id: pk of the just-created Booking.
    """
    try:
        booking = Booking.objects.select_related("property__owner", "tenant").get(pk=booking_id)
    except Booking.DoesNotExist:
        logger.warning("send_new_booking_request_email_task: Booking %s no longer exists.", booking_id)
        return

    try:
        send_new_booking_request_email(booking)
    except Exception as exc:
        raise self.retry(exc=exc)
