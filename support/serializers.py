from rest_framework import serializers

from common.validators import no_html_tags_validator
from support.models import Message, Ticket


class TicketSerializer(serializers.ModelSerializer):
    """
    Read/write representation of a Ticket.

    ``user``/``assigned_to`` are server-controlled: the opener is taken from the request user on
    create, and assignment happens automatically (see TicketViewSet.perform_create) - never chosen
    by the client. ``subject`` is only meaningful at creation; update() below only ever applies a
    ``status`` change, since that's the only mutation a support agent is allowed to make.
    """

    user = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(read_only=True)
    subject = serializers.CharField(max_length=255, validators=[no_html_tags_validator])

    class Meta:
        model = Ticket
        fields = ["id", "user", "assigned_to", "subject", "status", "created_at"]
        read_only_fields = ["id", "user", "assigned_to", "created_at"]

    def update(self, instance: Ticket, validated_data: dict) -> Ticket:
        """
        :param instance: the Ticket being updated.
        :param validated_data: validated input; only ``status`` is ever applied.
        :return: the updated Ticket.
        """
        if "status" in validated_data:
            instance.status = validated_data["status"]
            instance.save(update_fields=["status"])
        return instance


class MessageSerializer(serializers.ModelSerializer):
    """Read/write representation of a Message. ``ticket``/``sender`` are set by the view, not the client."""

    sender = serializers.PrimaryKeyRelatedField(read_only=True)
    body = serializers.CharField(validators=[no_html_tags_validator])

    class Meta:
        model = Message
        fields = ["id", "ticket", "sender", "body", "created_at"]
        read_only_fields = ["id", "ticket", "sender", "created_at"]
