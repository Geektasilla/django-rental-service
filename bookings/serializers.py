from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from bookings.models import Booking
from common.utils import as_drf_validation_error
from listings.models import Property


class BookingSerializer(serializers.ModelSerializer):
    """
    Read/write representation of a Booking.

    ``tenant``, ``status`` and ``price_frozen`` are server-controlled: the tenant is taken from
    the request user on create, status only ever changes through the confirm/cancel actions
    (BookingViewSet), and price_frozen is copied from the Property by Booking.save().
    """

    tenant = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "property",
            "tenant",
            "start_date",
            "end_date",
            "status",
            "price_frozen",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "status", "price_frozen", "created_at", "updated_at"]

    def create(self, validated_data: dict) -> Booking:
        """
        :param validated_data: validated input (property, start_date, end_date).
        :return: the newly created, PENDING Booking.
        :raises rest_framework.exceptions.ValidationError: if Booking.clean() rejects the date
            range (overlap with an existing BOOKED/PAID booking, or end_date <= start_date), or if
            a rare write conflict is detected while the property row is locked.

        Locks the Property row for the duration of the transaction (select_for_update) so two
        concurrent requests for overlapping dates can't both pass the overlap check in
        Booking.clean() before either commits - a no-op on SQLite, which has no row locking but
        already serializes writes at the database-file level.
        """
        try:
            with transaction.atomic():
                property_obj = Property.objects.select_for_update().get(pk=validated_data["property"].pk)
                booking = Booking.objects.create(
                    tenant=self.context["request"].user,
                    property=property_obj,
                    start_date=validated_data["start_date"],
                    end_date=validated_data["end_date"],
                )
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        except IntegrityError:
            raise serializers.ValidationError(
                {"detail": "This property is already booked for the selected dates."}
            )
        return booking
