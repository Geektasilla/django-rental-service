from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from common.tests.factories import make_owner, make_property
from listings.models import Property


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PropertyVisibilityTests(TestCase):
    """
    get_queryset() draws the line guests/other users only see APPROVED+is_active listings; an
    owner additionally sees their own regardless of status; staff/moderators see everything.
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.stranger = make_owner(email="stranger@example.com")
        self.approved = make_property(
            self.owner, title="Approved flat", moderation_status=Property.ModerationStatusChoices.APPROVED
        )
        self.pending = make_property(
            self.owner, title="Pending flat", moderation_status=Property.ModerationStatusChoices.PENDING
        )
        self.client = APIClient()

    def test_guest_sees_only_approved_active_listings(self) -> None:
        response = self.client.get("/api/v1/listings/")
        self.assertEqual(response.status_code, 200, response.data)
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(self.approved.pk, returned_ids)
        self.assertNotIn(self.pending.pk, returned_ids)

    def test_stranger_does_not_see_someone_elses_pending_listing(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/v1/listings/")
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.pending.pk, returned_ids)

    def test_owner_sees_their_own_pending_listing(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/listings/")
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertIn(self.pending.pk, returned_ids)
