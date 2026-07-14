from datetime import date, timedelta

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from bookings.models import Booking, BookingStatusChoices
from common.tests.factories import make_owner, make_property, make_tenant
from support.models import Ticket


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class AccountDeletionTests(TestCase):
    """
    GDPR Art. 17 right-to-erasure vs. HGB/AO record-retention law: Booking.tenant/Ticket.user are
    PROTECT, so the account can't be hard-deleted while it has that history - this endpoint
    anonymizes instead. See tools/issues.md Issue #21 for the full field-by-field rationale.
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.tenant = make_tenant()
        self.property = make_property(self.owner)
        self.booking = Booking.objects.create(
            property=self.property,
            tenant=self.tenant,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status=BookingStatusChoices.PAID,
        )
        Ticket.objects.create(user=self.tenant, subject="Help", status=Ticket.StatusChoices.OPEN)
        self.client = APIClient()

    def test_anonymize_scrubs_pii_but_keeps_protected_history(self) -> None:
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(
            "/api/v1/users/me/delete-account/", {"password": "TestPass123!"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.tenant.refresh_from_db()
        self.assertTrue(self.tenant.email.startswith("deleted-user-"))
        self.assertEqual(self.tenant.first_name, "")
        self.assertFalse(self.tenant.is_active)
        self.assertFalse(self.tenant.has_usable_password())

        self.tenant.tenant_profile.refresh_from_db()
        self.assertEqual(self.tenant.tenant_profile.passport_data, "")

        # Booking/Ticket survive (PROTECT) - the transactional history is retained per German law,
        # just now pointing at the anonymized account.
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.tenant_id, self.tenant.pk)
        self.assertTrue(Ticket.objects.filter(user=self.tenant).exists())

    def test_wrong_password_rejected_and_nothing_changes(self) -> None:
        self.client.force_authenticate(user=self.tenant)
        response = self.client.post(
            "/api/v1/users/me/delete-account/", {"password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.email, "tenant@example.com")
        self.assertTrue(self.tenant.is_active)

    def test_requires_authentication(self) -> None:
        response = self.client.post(
            "/api/v1/users/me/delete-account/", {"password": "TestPass123!"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
