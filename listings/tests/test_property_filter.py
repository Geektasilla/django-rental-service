from django.test import TestCase

from common.tests.factories import make_owner, make_property
from listings.filters import PropertyFilter
from listings.models import Property


class PropertyFilterTests(TestCase):
    """
    PropertyFilter.filter_price_min/max match against whichever price field is populated
    (price_per_day for DAILY, price_per_month for LONG_TERM), so these tests exercise both rent
    types through the same price_min/price_max params.
    """

    def setUp(self) -> None:
        owner = make_owner()
        self.cheap_daily = make_property(owner, title="Cheap daily", price_per_day="30.00", rooms_count=1)
        self.expensive_daily = make_property(owner, title="Expensive daily", price_per_day="200.00", rooms_count=4)
        self.long_term = make_property(
            owner,
            title="Long-term flat",
            rent_type=Property.RentTypeChoices.LONG_TERM,
            price_per_day=None,
            price_per_month="900.00",
            rooms_count=3,
        )

    def _filtered_ids(self, params: dict) -> list[int]:
        queryset = PropertyFilter(params, queryset=Property.objects.all()).qs
        return list(queryset.values_list("pk", flat=True))

    def test_price_min_matches_either_price_field(self) -> None:
        result_ids = self._filtered_ids({"price_min": "100"})
        self.assertIn(self.expensive_daily.pk, result_ids)
        self.assertIn(self.long_term.pk, result_ids)
        self.assertNotIn(self.cheap_daily.pk, result_ids)

    def test_price_max_matches_either_price_field(self) -> None:
        result_ids = self._filtered_ids({"price_max": "50"})
        self.assertIn(self.cheap_daily.pk, result_ids)
        self.assertNotIn(self.expensive_daily.pk, result_ids)
        self.assertNotIn(self.long_term.pk, result_ids)

    def test_rooms_range_filters_by_rooms_count(self) -> None:
        result_ids = self._filtered_ids({"rooms_min": "3", "rooms_max": "4"})
        self.assertCountEqual(result_ids, [self.expensive_daily.pk, self.long_term.pk])
