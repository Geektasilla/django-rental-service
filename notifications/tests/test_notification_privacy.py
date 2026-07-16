from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from common.tests.factories import make_tenant
from notifications.models import Notification


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class NotificationPrivacyTests(TestCase):
    """
    NotificationViewSet deliberately filters ``user=request.user`` by hand instead of reusing
    common.utils.visible_to_participants (that helper's staff-bypass would leak every user's
    private notifications to any staff account - see tools/issues.md Issue #21). This is the one
    thing that must never regress.
    """

    def setUp(self) -> None:
        self.owner = make_tenant(email="owner@example.com")
        self.other = make_tenant(email="other@example.com")
        self.own_notification = Notification.objects.create(
            user=self.owner, message="Your booking was confirmed."
        )
        Notification.objects.create(
            user=self.other, message="Someone else's notification."
        )
        self.client = APIClient()

    def test_list_only_returns_own_notifications(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, 200, response.data)
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(returned_ids, [self.own_notification.pk])

    def test_cannot_retrieve_someone_elses_notification_directly(self) -> None:
        self.client.force_authenticate(user=self.owner)
        other_notification = Notification.objects.get(user=self.other)
        response = self.client.get(f"/api/v1/notifications/{other_notification.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_mark_own_notification_as_read(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.patch(
            f"/api/v1/notifications/{self.own_notification.pk}/",
            {"is_read": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.own_notification.refresh_from_db()
        self.assertTrue(self.own_notification.is_read)
