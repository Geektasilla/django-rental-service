from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from analytics.models import SearchHistory
from common.tests.factories import make_tenant


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PopularSearchesTests(TestCase):
    """
    PopularSearchesView is AllowAny and aggregates SearchHistory across every user and guest - the
    one thing that must never happen is per-user data leaking through (search_query grouped by
    user_id would deanonymize who searched for what).
    """

    def setUp(self) -> None:
        self.tenant = make_tenant()
        # Two searches for "berlin" (one by a logged-in user, one by a guest), one for "munich".
        SearchHistory.objects.create(user=self.tenant, search_query="berlin")
        SearchHistory.objects.create(user=None, search_query="berlin")
        SearchHistory.objects.create(user=None, search_query="munich")
        self.client = APIClient()

    def test_accessible_without_authentication(self) -> None:
        response = self.client.get("/api/v1/analytics/popular-searches/")
        self.assertEqual(response.status_code, 200, response.data)

    def test_aggregates_counts_across_users_and_guests_ordered_by_frequency(self) -> None:
        response = self.client.get("/api/v1/analytics/popular-searches/")
        results = response.data["results"] if "results" in response.data else response.data
        by_query = {row["search_query"]: row["count"] for row in results}
        self.assertEqual(by_query["berlin"], 2)
        self.assertEqual(by_query["munich"], 1)
        # Most frequent first.
        self.assertEqual(results[0]["search_query"], "berlin")

    def test_response_never_exposes_per_user_identity(self) -> None:
        response = self.client.get("/api/v1/analytics/popular-searches/")
        results = response.data["results"] if "results" in response.data else response.data
        for row in results:
            self.assertEqual(set(row.keys()), {"search_query", "count"})
