from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import User
from users.models.agent import AgentProfile
from users.models.owner import OwnerProfile


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class OwnerProfileSelfServiceTests(TestCase):
    """
    Self-service OwnerProfile creation - previously the only way to create one was through
    /admin/ or seed_data.py, meaning no real registered user could actually become a functioning
    owner through the API alone.
    """

    def setUp(self) -> None:
        self.owner_flagged_user = User.objects.create_user(
            email="owner@example.com",
            password="TestPass123!",
            phone="+491701234580",
            is_owner=True,
        )
        self.plain_user = User.objects.create_user(
            email="plain@example.com", password="TestPass123!", phone="+491701234581"
        )
        self.client = APIClient()

    def test_user_without_owner_flag_cannot_create_profile(self) -> None:
        self.client.force_authenticate(user=self.plain_user)
        response = self.client.post(
            "/api/v1/users/me/owner-profile/", {"tax_id": "DE123456789"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_flagged_user_creates_profile(self) -> None:
        self.client.force_authenticate(user=self.owner_flagged_user)
        response = self.client.post(
            "/api/v1/users/me/owner-profile/", {"tax_id": "DE123456789"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(response.data["is_verified"])  # not writable, defaults False

    def test_cannot_create_duplicate_profile(self) -> None:
        OwnerProfile.objects.create(user=self.owner_flagged_user, tax_id="DE1")
        self.client.force_authenticate(user=self.owner_flagged_user)
        response = self.client.post(
            "/api/v1/users/me/owner-profile/", {"tax_id": "DE2"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_is_verified_cannot_be_set_by_the_user(self) -> None:
        self.client.force_authenticate(user=self.owner_flagged_user)
        response = self.client.post(
            "/api/v1/users/me/owner-profile/",
            {"tax_id": "DE123456789", "is_verified": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(response.data["is_verified"])

    def test_owner_can_view_and_update_own_profile(self) -> None:
        OwnerProfile.objects.create(user=self.owner_flagged_user, tax_id="DE1")
        self.client.force_authenticate(user=self.owner_flagged_user)

        get_response = self.client.get("/api/v1/users/me/owner-profile/")
        self.assertEqual(get_response.status_code, 200, get_response.data)

        patch_response = self.client.patch(
            "/api/v1/users/me/owner-profile/", {"bio": "Updated bio."}, format="json"
        )
        self.assertEqual(patch_response.status_code, 200, patch_response.data)
        self.assertEqual(patch_response.data["bio"], "Updated bio.")

    def test_user_without_profile_gets_404_on_get(self) -> None:
        self.client.force_authenticate(user=self.owner_flagged_user)
        response = self.client.get("/api/v1/users/me/owner-profile/")
        self.assertEqual(response.status_code, 404)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class ModeratorVerificationTests(TestCase):
    """Only a moderator can flip OwnerProfile.is_verified / AgentProfile.is_certified - the user's
    own POST to the self-service endpoint above can never do this (see test above)."""

    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            email="owner2@example.com",
            password="TestPass123!",
            phone="+491701234582",
            is_owner=True,
        )
        self.agent = User.objects.create_user(
            email="agent@example.com",
            password="TestPass123!",
            phone="+491701234583",
            is_agent=True,
        )
        self.moderator = User.objects.create_user(
            email="mod@example.com",
            password="TestPass123!",
            phone="+491701234584",
            is_moderator=True,
        )
        self.owner_profile = OwnerProfile.objects.create(user=self.owner, tax_id="DE1")
        self.agent_profile = AgentProfile.objects.create(
            user=self.agent, company_name="Agency GmbH", license_number="LIC-1"
        )
        self.client = APIClient()

    def test_moderator_verifies_owner(self) -> None:
        self.client.force_authenticate(user=self.moderator)
        response = self.client.post(
            f"/api/v1/users/{self.owner.pk}/owner-profile/verify/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.owner_profile.refresh_from_db()
        self.assertTrue(self.owner_profile.is_verified)
        self.assertIsNotNone(self.owner_profile.verified_at)

    def test_moderator_certifies_agent(self) -> None:
        self.client.force_authenticate(user=self.moderator)
        response = self.client.post(
            f"/api/v1/users/{self.agent.pk}/agent-profile/certify/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.agent_profile.refresh_from_db()
        self.assertTrue(self.agent_profile.is_certified)

    def test_non_moderator_cannot_verify(self) -> None:
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(
            f"/api/v1/users/{self.owner.pk}/owner-profile/verify/"
        )
        self.assertEqual(response.status_code, 403)

    def test_verify_returns_404_for_user_without_profile(self) -> None:
        other = User.objects.create_user(
            email="noprofile@example.com",
            password="TestPass123!",
            phone="+491701234585",
        )
        self.client.force_authenticate(user=self.moderator)
        response = self.client.post(f"/api/v1/users/{other.pk}/owner-profile/verify/")
        self.assertEqual(response.status_code, 404)
