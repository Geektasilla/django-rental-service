from datetime import date, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from bookings.models import Booking, BookingStatusChoices
from bookings.permissions import CanCancelBooking, IsBookingPropertyOwner, IsBookingTenant
from bookings.serializers import BookingSerializer
from common.utils import as_drf_validation_error, visible_to_participants
from listings.models import Property
from reviews.serializers import ReviewSerializer
from users.permissions import IsTenant

CANCELLATION_NOTICE_DAYS = 21


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Create/list/retrieve bookings, plus confirm/cancel actions.

    No update/destroy: a booking's status only ever changes through confirm/cancel, never a
    direct PATCH, and bookings are never deleted (Booking.property is on_delete=PROTECT).
    """

    serializer_class = BookingSerializer

    def get_permissions(self) -> list:
        """
        :return: instantiated permission objects for the current action - only an ACTIVE tenant
            may request a booking (owners/agents can't book their own or anyone else's listing);
            confirming requires the listing's owner/agent; cancelling requires being the tenant
            or the listing's owner.
        """
        if self.action == "create":
            permission_classes = [IsAuthenticated, IsTenant]
        elif self.action == "confirm":
            permission_classes = [IsAuthenticated, IsBookingPropertyOwner]
        elif self.action == "cancel":
            permission_classes = [IsAuthenticated, CanCancelBooking]
        elif self.action == "review":
            permission_classes = [IsAuthenticated, IsBookingTenant]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self) -> QuerySet:
        """
        :return: bookings visible to the current user - their own as a tenant, bookings made on
            their own listings as an owner/agent, or everything for staff.
        """
        queryset = Booking.objects.select_related("property__owner", "tenant")
        return visible_to_participants(queryset, self.request.user, "tenant", "property__owner")

    @action(detail=True, methods=["post"])
    def confirm(self, request: Request, pk: str | None = None) -> Response:
        """
        Approve a PENDING booking (-> BOOKED), then auto-decline every other PENDING request on
        the same property whose date range overlaps this one.

        Locks the Property row for the duration of the transaction (select_for_update), same
        pattern as BookingSerializer.create() - two owners/agents confirming different
        overlapping PENDING requests on the same property at the same time can't both pass
        Booking.clean() before either commits.
        """
        booking = self.get_object()
        try:
            with transaction.atomic():
                Property.objects.select_for_update().get(pk=booking.property_id)
                booking.refresh_from_db()
                if booking.status != BookingStatusChoices.PENDING:
                    return Response(
                        {"detail": "Only a pending booking can be confirmed."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                booking.status = BookingStatusChoices.BOOKED
                booking.save()

                Booking.objects.filter(
                    property_id=booking.property_id,
                    status=BookingStatusChoices.PENDING,
                    start_date__lt=booking.end_date,
                    end_date__gt=booking.start_date,
                ).exclude(pk=booking.pk).update(status=BookingStatusChoices.CANCELLED)
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        except IntegrityError:
            raise serializers.ValidationError(
                {"detail": "This property is already booked for the selected dates."}
            )

        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        """
        Cancel a booking (-> CANCELLED). A still-PENDING request can be withdrawn/declined by
        either party at any time; a confirmed BOOKED/PAID booking may only be cancelled more than
        CANCELLATION_NOTICE_DAYS before start_date - no refund logic, there's no payment gateway
        in this project.
        """
        booking = self.get_object()
        if booking.status == BookingStatusChoices.CANCELLED:
            return Response(
                {"detail": "This booking is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if booking.status in (BookingStatusChoices.BOOKED, BookingStatusChoices.PAID):
            if date.today() + timedelta(days=CANCELLATION_NOTICE_DAYS) >= booking.start_date:
                return Response(
                    {"detail": f"A confirmed booking can only be cancelled more than "
                               f"{CANCELLATION_NOTICE_DAYS} days before the start date."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        booking.status = BookingStatusChoices.CANCELLED
        booking.save()
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def review(self, request: Request, pk: str | None = None) -> Response:
        """
        Leave a review for this booking. ``IsBookingTenant`` already restricts this to the
        booking's own tenant; Review.clean() enforces status == PAID and the 90-day window.
        """
        booking = self.get_object()
        if hasattr(booking, "review"):
            return Response(
                {"detail": "This booking has already been reviewed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(booking=booking)
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
