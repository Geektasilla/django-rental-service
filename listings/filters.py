import django_filters as filters
from django.db.models import Q, QuerySet

from listings.models import Property


class PropertyFilter(filters.FilterSet):
    """
    Filter set for GET /api/v1/listings/.

    price_min/price_max match against whichever price field is populated (price_per_day for
    DAILY, price_per_month for LONG_TERM - Property.clean() guarantees exactly one is set), so a
    single price range works across both rent types without the caller needing to know which.
    """

    price_min = filters.NumberFilter(method="filter_price_min")
    price_max = filters.NumberFilter(method="filter_price_max")
    rooms_min = filters.NumberFilter(field_name="rooms_count", lookup_expr="gte")
    rooms_max = filters.NumberFilter(field_name="rooms_count", lookup_expr="lte")
    city = filters.CharFilter(field_name="location__address__postal_code__city", lookup_expr="iexact")

    class Meta:
        model = Property
        fields = ["category", "rent_type", "listed_as"]

    def filter_price_min(self, queryset: QuerySet, name: str, value) -> QuerySet:
        """
        :param queryset: the queryset being filtered.
        :param name: unused, required by django-filter's method-filter signature.
        :param value: minimum price (inclusive) in EUR.
        :return: listings whose active price field is at least ``value``.
        """
        return queryset.filter(Q(price_per_day__gte=value) | Q(price_per_month__gte=value))

    def filter_price_max(self, queryset: QuerySet, name: str, value) -> QuerySet:
        """
        :param queryset: the queryset being filtered.
        :param name: unused, required by django-filter's method-filter signature.
        :param value: maximum price (inclusive) in EUR.
        :return: listings whose active price field is at most ``value``.
        """
        return queryset.filter(Q(price_per_day__lte=value) | Q(price_per_month__lte=value))
