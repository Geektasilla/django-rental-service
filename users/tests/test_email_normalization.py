from django.test import TestCase

from users.models import User


class EmailNormalizationTests(TestCase):
    """
    UserManager.create_user() runs the address through normalize_email() (users/models/base_user.py),
    which lower-cases the domain part only - the local part (before @) is left as-is, matching
    Django's own normalize_email() behavior.
    """

    def test_domain_is_lowercased_on_create_user(self) -> None:
        user = User.objects.create_user(email="Tenant@EXAMPLE.COM", password="TestPass123!", phone="+491700000001")
        self.assertEqual(user.email, "Tenant@example.com")

    def test_already_lowercase_email_is_unchanged(self) -> None:
        user = User.objects.create_user(email="owner@example.com", password="TestPass123!", phone="+491700000002")
        self.assertEqual(user.email, "owner@example.com")
