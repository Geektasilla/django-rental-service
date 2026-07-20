from django.conf import settings
from django.utils.translation import gettext_lazy as _

from common.services.email import send_email


def send_new_booking_request_email(booking) -> bool:
    """
    Notify a property's owner by email that a new booking request came in.

    Called from bookings/tasks.py (a Celery task), never directly from the post_save signal -
    swallow_errors=False lets a transient SMTP failure raise so the task can retry instead of
    silently dropping the email.

    :param booking: the newly created Booking (property/tenant already select_related by the caller).
    :return: True if the email was sent.
    """
    owner_name = booking.property.owner.first_name or booking.property.owner.email
    return send_email(
        subject=str(
            _("New booking request for %(title)s") % {"title": booking.property.title}
        ),
        message=str(
            _(
                "Hello %(owner)s,\n\n"
                "%(tenant)s requested to book %(title)s from %(start)s to %(end)s "
                "for %(price)s. Review the request: %(link)s\n\n"
                "If you have any questions, please contact our support team via the "
                "app's support section."
            )
            % {
                "owner": owner_name,
                "tenant": booking.tenant.email,
                "title": booking.property.title,
                "start": booking.start_date,
                "end": booking.end_date,
                "price": booking.price_frozen,
                "link": f"{settings.FRONTEND_URL}/bookings/{booking.pk}",
            }
        ),
        to=booking.property.owner.email,
        swallow_errors=False,
    )
