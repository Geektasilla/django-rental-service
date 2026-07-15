from django.db.models import Count, QuerySet
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from analytics.models import SearchHistory
from analytics.serializers import PopularSearchSerializer


class PopularSearchesView(ListAPIView):
    """
    Most-searched queries, aggregated across all users and guests.

    AllowAny, same as the popularity sort on listings: this is anonymized, aggregate data with
    no per-user attribution, meant to help guests discover what to search for.
    """

    serializer_class = PopularSearchSerializer
    permission_classes = [AllowAny]

    def get_queryset(self) -> QuerySet:
        """:return: distinct search queries with their usage count, most frequent first."""
        return (
            SearchHistory.objects.values("search_query")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
