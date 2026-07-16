from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings

from bookings.models import Booking, BookingStatusChoices
from common.tests.factories import make_owner, make_property, make_tenant
from reviews.models import Review


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ReviewRatingRangeTests(TestCase):
    """
    rating must stay within 1-5, enforced both by validators (caught via clean()/full_clean() on
    normal save()) and by the review_rating_range CheckConstraint (the only thing left to catch it
    if clean() is bypassed, e.g. via bulk_create()).
    """

    def setUp(self) -> None:
        owner = make_owner()
        tenant = make_tenant()
        property_ = make_property(owner)
        self.booking = Booking.objects.create(
            property=property_,
            tenant=tenant,
            start_date=date.today() - timedelta(days=5),
            end_date=date.today() - timedelta(days=3),
            status=BookingStatusChoices.PAID,
        )

    def test_rating_within_range_allowed(self) -> None:
        review = Review.objects.create(booking=self.booking, rating=5, comment="Great stay.")
        self.assertEqual(review.rating, 5)

    def test_rating_below_one_blocked_through_normal_save(self) -> None:
        with self.assertRaises(ValidationError):
            Review.objects.create(booking=self.booking, rating=0, comment="Too low.")

    def test_rating_above_five_blocked_through_normal_save(self) -> None:
        with self.assertRaises(ValidationError):
            Review.objects.create(booking=self.booking, rating=6, comment="Too high.")

    def test_constraint_blocks_out_of_range_rating_bypassing_clean_via_bulk_create(self) -> None:
        out_of_range_review = Review(booking=self.booking, rating=6, comment="Bypassing clean().")
        with self.assertRaises(IntegrityError):
            Review.objects.bulk_create([out_of_range_review])
