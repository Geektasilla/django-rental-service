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
class BookingPermissionBoundaryTests(TestCase):
    """A handful of "stranger can't touch it" checks - the object-level permissions are the main
    thing standing between tenants seeing/confirming each other's bookings."""

    def setUp(self) -> None:
        self.owner = make_owner()
        self.tenant = make_tenant(email="tenant1@example.com")
        self.stranger = make_tenant(email="stranger@example.com")
        self.property = make_property(self.owner)
        self.booking = Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status=BookingStatusChoices.PENDING,
        )
        self.client = APIClient()

    def test_stranger_cannot_see_someone_elses_booking_in_list(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/v1/bookings/")
        self.assertEqual(response.status_code, 200, response.data)
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.booking.pk, returned_ids)

    def test_stranger_cannot_confirm_someone_elses_booking(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/confirm/")
        self.assertEqual(response.status_code, 404)  # not visible -> not found, not 403

    def test_owner_of_the_property_can_confirm_it(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/confirm/")
        self.assertEqual(response.status_code, 200, response.data)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatusChoices.BOOKED)

    def test_owner_cannot_book_their_own_listing(self) -> None:
        """IsTenant requires an ACTIVE TenantProfile - an owner-only account has none."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            "/api/v1/bookings/",
            {
                "property": self.property.pk,
                "start_date": str(date.today() + timedelta(days=10)),
                "end_date": str(date.today() + timedelta(days=12)),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class UnverifiedOwnerCannotConfirmTests(TestCase):
    """
    OwnerIsVerifiedToConfirm: blocking this at confirm() (not the later pay() stub) is what
    actually protects a tenant from being told "go ahead and pay" by an unverified/scam account -
    by the time pay() would run, real money (sent outside the system) has already moved.
    """

    def setUp(self) -> None:
        self.unverified_owner = make_owner(verified=False)
        self.tenant = make_tenant()
        self.property = make_property(self.unverified_owner)
        self.booking = Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status=BookingStatusChoices.PENDING,
        )
        self.client = APIClient()

    def test_unverified_owner_cannot_confirm(self) -> None:
        self.client.force_authenticate(user=self.unverified_owner)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/confirm/")
        self.assertEqual(response.status_code, 403)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatusChoices.PENDING)

    def test_owner_can_confirm_once_verified(self) -> None:
        self.unverified_owner.owner_profile.is_verified = True
        self.unverified_owner.owner_profile.save(update_fields=["is_verified"])

        self.client.force_authenticate(user=self.unverified_owner)
        response = self.client.post(f"/api/v1/bookings/{self.booking.pk}/confirm/")
        self.assertEqual(response.status_code, 200, response.data)
