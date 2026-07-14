from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from notifications.models import Notification

from .models import Booking
from .tasks import send_new_booking_request_email_task


@receiver(post_save, sender=Booking)
def notify_owner_of_new_booking(sender, instance: Booking, created: bool, **kwargs) -> None:
    """
    On booking creation, notify the property's owner in-app immediately and queue the email send.

    Only the email is deferred to Celery - the in-app Notification is a cheap local DB write and
    stays synchronous so it's visible to the owner the moment this request returns. The email send
    is queued rather than sent inline because it's an external network call that must not block
    (or fail) the request-response cycle; bookings/tasks.py handles retries on SMTP failure.

    :param sender: the Booking model class.
    :param instance: the saved Booking.
    :param created: True only for the initial insert.
    """
    if not created:
        return

    Notification.objects.create(
        user=instance.property.owner,
        message=str(
            _("New booking request for %(title)s from %(start)s to %(end)s.")
            % {"title": instance.property.title, "start": instance.start_date, "end": instance.end_date}
        ),
    )
    send_new_booking_request_email_task.delay(instance.pk)
