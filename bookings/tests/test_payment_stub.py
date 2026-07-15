from datetime import date, timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from bookings.models import Booking, BookingStatusChoices
from common.tests.factories import make_owner, make_property, make_tenant


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class PaymentStubTests(TestCase):
    """
    POST /bookings/{id}/pay/ - manual payment-confirmation stub (no real payment gateway in this
    project). Only the listing's owner may confirm payment was received; this is what unblocks
    Review creation (Review.clean() requires status == PAID) through the real API instead of only
    through test fixtures / seed_data's direct ORM writes.
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.tenant = make_tenant()
        self.stranger = make_tenant(email="stranger@example.com")
        self.property = make_property(self.owner)
        self.booking = Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() - timedelta(days=2),
            status=BookingStatusChoices.BOOKED,
        )
        self.client = APIClient()

    def test_owner_marks_booking_paid(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/pay/")
        self.assertEqual(response.status_code, 200, response.data)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatusChoices.PAID)

    def test_tenant_cannot_mark_own_booking_paid(self) -> None:
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/pay/")
        self.assertEqual(response.status_code, 403)

    def test_stranger_cannot_mark_booking_paid(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/pay/")
        self.assertEqual(response.status_code, 404)

    def test_only_booked_can_be_marked_paid(self) -> None:
        self.booking.status = BookingStatusChoices.PENDING
        self.booking.save()
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/pay/")
        self.assertEqual(response.status_code, 400)

    def test_paid_booking_can_then_be_reviewed_by_tenant(self) -> None:
        self.client.force_authenticate(user=self.owner)
        pay_response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/pay/")
        self.assertEqual(pay_response.status_code, 200, pay_response.data)

        self.client.force_authenticate(user=self.tenant)
        review_response = self.client.post(
            f"/api/v1/bookings/{self.booking.pk}/review/",
            {"rating": 5, "comment": "Great stay."},
            format="json",
        )
        self.assertEqual(review_response.status_code, 201, review_response.data)
