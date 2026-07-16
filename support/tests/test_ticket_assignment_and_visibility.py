from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from common.tests.factories import make_tenant
from support.models import Ticket
from users.models import User


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TicketAssignmentTests(TestCase):
    """TicketViewSet.perform_create auto-assigns the active support agent with the fewest open tickets."""

    def setUp(self) -> None:
        self.opener = make_tenant()
        self.busy_agent = User.objects.create_user(
            email="busy@example.com",
            password="TestPass123!",
            phone="+491700000001",
            is_support=True,
        )
        self.free_agent = User.objects.create_user(
            email="free@example.com",
            password="TestPass123!",
            phone="+491700000002",
            is_support=True,
        )
        # Give the busy agent an existing open ticket so the free agent has fewer.
        Ticket.objects.create(
            user=self.opener,
            assigned_to=self.busy_agent,
            subject="Existing",
            status=Ticket.StatusChoices.OPEN,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.opener)

    def test_new_ticket_assigned_to_agent_with_fewest_open_tickets(self) -> None:
        response = self.client.post(
            "/api/v1/support/",
            {"subject": "Need help", "status": "open"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual(ticket.assigned_to_id, self.free_agent.pk)

    def test_ticket_left_unassigned_when_no_agent_exists(self) -> None:
        User.objects.filter(is_support=True).update(is_support=False)
        response = self.client.post(
            "/api/v1/support/",
            {"subject": "No agents available", "status": "open"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertIsNone(ticket.assigned_to)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TicketVisibilityTests(TestCase):
    """A stranger (not the opener, not the assigned agent, not staff) must never see the ticket."""

    def setUp(self) -> None:
        self.opener = make_tenant()
        self.stranger = make_tenant(email="stranger@example.com")
        self.agent = User.objects.create_user(
            email="agent@example.com",
            password="TestPass123!",
            phone="+491700000003",
            is_support=True,
        )
        self.ticket = Ticket.objects.create(
            user=self.opener,
            assigned_to=self.agent,
            subject="Private issue",
            status=Ticket.StatusChoices.OPEN,
        )
        self.client = APIClient()

    def test_stranger_cannot_see_ticket_in_list(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get("/api/v1/support/")
        returned_ids = [item["id"] for item in response.data["results"]]
        self.assertNotIn(self.ticket.pk, returned_ids)

    def test_stranger_cannot_retrieve_ticket_directly(self) -> None:
        self.client.force_authenticate(user=self.stranger)
        response = self.client.get(f"/api/v1/support/{self.ticket.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_assigned_agent_can_see_and_reply_to_the_ticket(self) -> None:
        self.client.force_authenticate(user=self.agent)
        response = self.client.get(f"/api/v1/support/{self.ticket.pk}/")
        self.assertEqual(response.status_code, 200, response.data)

        reply = self.client.post(
            f"/api/v1/support/{self.ticket.pk}/messages/",
            {"body": "How can I help?"},
            format="json",
        )
        self.assertEqual(reply.status_code, 201, reply.data)
