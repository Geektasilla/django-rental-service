from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import User
from users.tokens import email_verification_token_generator, encode_uid, password_reset_token_generator


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PasswordResetTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="reset@example.com", password="OldPass123!", phone="+491701234570"
        )
        self.client = APIClient()

    def test_request_responds_200_regardless_of_whether_the_email_exists(self) -> None:
        """Anti user-enumeration: a registered and an unregistered email get an identical response."""
        for email in ("reset@example.com", "doesnotexist@example.com"):
            response = self.client.post("/api/v1/auth/password-reset/request/", {"email": email}, format="json")
            self.assertEqual(response.status_code, 200, response.data)

    def test_confirm_with_valid_token_changes_password_and_revokes_sessions(self) -> None:
        login_before = self.client.post(
            "/api/v1/auth/login/", {"email": "reset@example.com", "password": "OldPass123!"}, format="json"
        )
        old_refresh = login_before.data["refresh"]

        uid = encode_uid(self.user)
        token = password_reset_token_generator.make_token(self.user)
        confirm_response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": token, "new_password": "NewPass456!"},
            format="json",
        )
        self.assertEqual(confirm_response.status_code, 200, confirm_response.data)

        # Old sessions must not survive a password reset.
        refresh_response = self.client.post("/api/v1/auth/login/refresh/", {"refresh": old_refresh}, format="json")
        self.assertEqual(refresh_response.status_code, 401)

        # New password logs in; old one no longer works.
        new_login = self.client.post(
            "/api/v1/auth/login/", {"email": "reset@example.com", "password": "NewPass456!"}, format="json"
        )
        self.assertEqual(new_login.status_code, 200, new_login.data)
        old_login = self.client.post(
            "/api/v1/auth/login/", {"email": "reset@example.com", "password": "OldPass123!"}, format="json"
        )
        self.assertEqual(old_login.status_code, 401)

    def test_confirm_with_garbage_token_rejected(self) -> None:
        uid = encode_uid(self.user)
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"uid": uid, "token": "not-a-real-token", "new_password": "NewPass456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class EmailVerificationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="verify@example.com", password="TestPass123!", phone="+491701234571"
        )
        self.client = APIClient()

    def test_request_requires_authentication(self) -> None:
        response = self.client.post("/api/v1/users/me/email-verification/request/")
        self.assertEqual(response.status_code, 401)

    def test_confirm_with_valid_token_marks_email_verified(self) -> None:
        self.assertFalse(self.user.is_email_verified)
        uid = encode_uid(self.user)
        token = email_verification_token_generator.make_token(self.user)

        response = self.client.post(
            "/api/v1/auth/email-verification/confirm/", {"uid": uid, "token": token}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

        # The token's hash includes is_email_verified, so it self-invalidates after use.
        reuse_response = self.client.post(
            "/api/v1/auth/email-verification/confirm/", {"uid": uid, "token": token}, format="json"
        )
        self.assertEqual(reuse_response.status_code, 400)
