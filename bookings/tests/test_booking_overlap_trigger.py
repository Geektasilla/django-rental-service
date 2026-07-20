from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase, override_settings

from bookings.models import Booking, BookingStatusChoices
from common.tests.factories import make_owner, make_property, make_tenant


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class BookingOverlapTriggerTests(TestCase):
    """
    Booking.clean() already blocks overlapping BOOKED/PAID bookings on the same property, but that
    check is bypassed by bulk_create()/bulk_update()/.update() (they skip .save()/full_clean()
    entirely). The BEFORE INSERT/UPDATE DB triggers (bookings/migrations/
    0006_booking_overlap_triggers.py) are the only thing that still catches it in that case - this
    is the one permanent test for that SQLite trigger path (MySQL execution verified manually
    against the live server/container).
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.tenant = make_tenant()
        self.property = make_property(self.owner)
        self.start = date.today()
        self.end = self.start + timedelta(days=3)

    def test_clean_blocks_overlap_through_normal_save(self) -> None:
        Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=self.start,
            end_date=self.end,
            status=BookingStatusChoices.BOOKED,
        )
        with self.assertRaises(Exception):
            Booking.objects.create(
                property=self.property,
                tenant=self.tenant,
                start_date=self.start + timedelta(days=1),
                end_date=self.end + timedelta(days=1),
                status=BookingStatusChoices.BOOKED,
            )

    def test_trigger_blocks_overlap_bypassing_clean_via_bulk_create(self) -> None:
        Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=self.start,
            end_date=self.end,
            status=BookingStatusChoices.BOOKED,
        )
        overlapping = Booking(
            property=self.property,
            tenant=self.tenant,
            start_date=self.start + timedelta(days=1),
            end_date=self.end + timedelta(days=1),
            status=BookingStatusChoices.BOOKED,
            price_frozen="50.00",
        )
        with self.assertRaises(IntegrityError):
            Booking.objects.bulk_create([overlapping])

    def test_non_overlapping_bookings_on_the_same_property_are_allowed(self) -> None:
        Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=self.start,
            end_date=self.end,
            status=BookingStatusChoices.BOOKED,
        )
        second = Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=self.end + timedelta(days=1),
            end_date=self.end + timedelta(days=4),
            status=BookingStatusChoices.BOOKED,
        )
        self.assertIsNotNone(second.pk)
