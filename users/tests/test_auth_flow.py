from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import User


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AuthFlowTests(TestCase):
    """Register -> login -> refresh -> logout, the core session lifecycle every other endpoint relies on."""

    def setUp(self) -> None:
        self.client = APIClient()

    def test_register_creates_a_usable_account(self) -> None:
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newuser@example.com",
                "password": "TestPass123!",
                "phone": "+491701234567",
                "first_name": "New",
                "last_name": "User",
                "gender": "unspecified",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())
        # Privilege escalation guard: these fields must never be settable via public registration.
        user = User.objects.get(email="newuser@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_support)
        self.assertFalse(user.is_moderator)

    def test_login_then_refresh_then_logout(self) -> None:
        User.objects.create_user(email="user@example.com", password="TestPass123!", phone="+491701234568")

        login_response = self.client.post(
            "/api/v1/auth/login/", {"email": "user@example.com", "password": "TestPass123!"}, format="json"
        )
        self.assertEqual(login_response.status_code, 200, login_response.data)
        access = login_response.data["access"]
        refresh = login_response.data["refresh"]

        refresh_response = self.client.post("/api/v1/auth/login/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(refresh_response.status_code, 200, refresh_response.data)
        # ROTATE_REFRESH_TOKENS+BLACKLIST_AFTER_ROTATION: the old refresh is now dead, use the new one.
        rotated_refresh = refresh_response.data["refresh"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout_response = self.client.post("/api/v1/auth/logout/", {"refresh": rotated_refresh}, format="json")
        self.assertEqual(logout_response.status_code, 205, logout_response.data)

        # A blacklisted refresh token must not mint further access tokens.
        reuse_response = self.client.post("/api/v1/auth/login/refresh/", {"refresh": rotated_refresh}, format="json")
        self.assertEqual(reuse_response.status_code, 401)

    def test_login_with_wrong_password_rejected(self) -> None:
        User.objects.create_user(email="user2@example.com", password="TestPass123!", phone="+491701234569")
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "user2@example.com", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
