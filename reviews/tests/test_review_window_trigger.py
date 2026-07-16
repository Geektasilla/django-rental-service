from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase, override_settings

from bookings.models import Booking, BookingStatusChoices
from common.tests.factories import make_owner, make_property, make_tenant
from reviews.models import Review
from reviews.models.review import REVIEW_WINDOW_DAYS


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ReviewWindowTriggerTests(TestCase):
    """
    Review.clean() already blocks reviews on non-PAID or stale (>90 day) bookings, but that check
    is bypassed by bulk_create() (skips .save()/full_clean()). The BEFORE INSERT trigger
    (reviews/migrations/0002_review_window_trigger.py) is the only thing that still catches it in
    that case.
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.tenant = make_tenant()
        self.property = make_property(self.owner)

    def _make_booking(self, end_date, status=BookingStatusChoices.PAID) -> Booking:
        return Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=end_date - timedelta(days=2),
            end_date=end_date,
            status=status,
        )

    def test_review_within_window_allowed(self) -> None:
        booking = self._make_booking(end_date=date.today() - timedelta(days=10))
        review = Review.objects.create(booking=booking, rating=5, comment="Great stay.")
        self.assertIsNotNone(review.pk)

    def test_review_outside_window_blocked_through_normal_save(self) -> None:
        booking = self._make_booking(end_date=date.today() - timedelta(days=100))
        with self.assertRaises(Exception):
            Review.objects.create(booking=booking, rating=5, comment="Too late.")

    def test_trigger_blocks_stale_review_bypassing_clean_via_bulk_create(self) -> None:
        booking = self._make_booking(end_date=date.today() - timedelta(days=100))
        stale_review = Review(booking=booking, rating=5, comment="Bypassing clean().")
        with self.assertRaises(IntegrityError):
            Review.objects.bulk_create([stale_review])

    def test_trigger_blocks_review_on_non_paid_booking_bypassing_clean(self) -> None:
        booking = self._make_booking(
            end_date=date.today() - timedelta(days=1),
            status=BookingStatusChoices.BOOKED,
        )
        unpaid_review = Review(booking=booking, rating=5, comment="Never paid.")
        with self.assertRaises(IntegrityError):
            Review.objects.bulk_create([unpaid_review])


class ReviewWindowDaysCanaryTest(TestCase):
    """
    Not a behavior test - a tripwire. REVIEW_WINDOW_DAYS (reviews/models/review.py) must stay in
    sync with the hardcoded 90 in reviews/migrations/0002_review_window_trigger.py (the trigger
    can't read Python constants). If this fails, someone changed one without the other.
    """

    def test_review_window_days_matches_the_hardcoded_db_trigger_threshold(
        self,
    ) -> None:
        self.assertEqual(
            REVIEW_WINDOW_DAYS,
            90,
            "REVIEW_WINDOW_DAYS changed - update the hardcoded threshold in "
            "reviews/migrations/0002_review_window_trigger.py to match, then update this test.",
        )
