from datetime import date, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from bookings.models import Booking, BookingStatusChoices
from bookings.permissions import (
    CanCancelBooking,
    IsBookingPropertyOwner,
    IsBookingTenant,
    OwnerIsVerifiedToConfirm,
)
from bookings.serializers import BookingSerializer
from common.mixins import ActionPermissionsMixin
from common.utils import as_drf_validation_error, visible_to_participants
from listings.models import Property
from notifications.models import Notification
from reviews.serializers import ReviewSerializer
from users.permissions import IsTenant

CANCELLATION_NOTICE_DAYS = 21


def _notify(user, message: str) -> None:
    """
    Create an in-app Notification for ``user``.

    :param user: the recipient.
    :param message: the already-translated notification text.
    """
    Notification.objects.create(user=user, message=message)


class BookingViewSet(
    ActionPermissionsMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Create/list/retrieve bookings, plus confirm/pay/cancel actions.

    No update/destroy: a booking's status only ever changes through confirm/pay/cancel, never a
    direct PATCH, and bookings are never deleted (Booking.property is on_delete=PROTECT).
    """

    serializer_class = BookingSerializer
    # Only an ACTIVE tenant may request a booking (owners/agents can't book their own or anyone
    # else's listing); confirming requires the listing's owner/agent, plus - for owner-listed
    # properties only - a verified OwnerProfile (OwnerIsVerifiedToConfirm; see that class for why
    # this is checked at confirm, not at the later pay step); cancelling requires being the tenant
    # or the listing's owner.
    permission_classes_by_action = {
        "create": [IsAuthenticated, IsTenant],
        "confirm": [IsAuthenticated, IsBookingPropertyOwner, OwnerIsVerifiedToConfirm],
        "pay": [IsAuthenticated, IsBookingPropertyOwner],
        "cancel": [IsAuthenticated, CanCancelBooking],
        "review": [IsAuthenticated, IsBookingTenant],
    }

    def get_queryset(self) -> QuerySet:
        """
        :return: bookings visible to the current user - their own as a tenant, bookings made on
            their own listings as an owner/agent, or everything for staff.
        """
        if getattr(self, "swagger_fake_view", False):
            return Booking.objects.none()
        queryset = Booking.objects.select_related("property__owner", "tenant")
        return visible_to_participants(
            queryset, self.request.user, "tenant", "property__owner"
        )

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
                        {"detail": _("Only a pending booking can be confirmed.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                booking.status = BookingStatusChoices.BOOKED
                booking.save()

                competing_bookings = list(
                    Booking.objects.select_related("tenant").filter(
                        property_id=booking.property_id,
                        status=BookingStatusChoices.PENDING,
                        start_date__lt=booking.end_date,
                        end_date__gt=booking.start_date,
                    ).exclude(pk=booking.pk)
                )
                Booking.objects.filter(
                    pk__in=[competing_booking.pk for competing_booking in competing_bookings]
                ).update(status=BookingStatusChoices.CANCELLED)

                _notify(
                    booking.tenant,
                    str(
                        _("Your booking for %(title)s from %(start)s to %(end)s has been confirmed.")
                        % {
                            "title": booking.property.title,
                            "start": booking.start_date,
                            "end": booking.end_date,
                        }
                    ),
                )
                for competing_booking in competing_bookings:
                    _notify(
                        competing_booking.tenant,
                        str(
                            _(
                                "Your booking request for %(title)s from %(start)s to "
                                "%(end)s was declined because those dates are already booked."
                            )
                            % {
                                "title": booking.property.title,
                                "start": competing_booking.start_date,
                                "end": competing_booking.end_date,
                            }
                        ),
                    )
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        except IntegrityError:
            raise serializers.ValidationError(
                {"detail": _("This property is already booked for the selected dates.")}
            )

        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def pay(self, request: Request, pk: str | None = None) -> Response:
        """
        Manual payment-confirmation stub (BOOKED -> PAID) - there is no payment gateway in this
        project (no charge is made, no money moves anywhere). This is the integration point a
        real gateway would plug into later; for now the listing's owner/agent confirms payment
        was received by some means outside the system (e.g. bank transfer), the same way small
        rental platforms operate before adopting a payment processor.

        Deliberately not tenant-triggered: a tenant marking their own booking "paid" would assert
        payment happened with no actual transaction behind it. Restricting this to the same
        IsBookingPropertyOwner used by confirm() means only the party who'd actually receive the
        money can flip the flag.
        """
        booking = self.get_object()
        if booking.status != BookingStatusChoices.BOOKED:
            return Response(
                {"detail": _("Only a booked reservation can be marked as paid.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.status = BookingStatusChoices.PAID
        booking.save()
        _notify(
            booking.tenant,
            str(
                _("Payment for your booking of %(title)s has been confirmed.")
                % {"title": booking.property.title}
            ),
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
                {"detail": _("This booking is already cancelled.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if booking.status in (BookingStatusChoices.BOOKED, BookingStatusChoices.PAID):
            if (
                date.today() + timedelta(days=CANCELLATION_NOTICE_DAYS)
                >= booking.start_date
            ):
                return Response(
                    {
                        "detail": _(
                            "A confirmed booking can only be cancelled more than "
                            "%(days)d days before the start date."
                        )
                        % {"days": CANCELLATION_NOTICE_DAYS}
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        booking.status = BookingStatusChoices.CANCELLED
        booking.save()

        other_party = (
            booking.property.owner
            if request.user.id == booking.tenant_id
            else booking.tenant
        )
        _notify(
            other_party,
            str(
                _("The booking for %(title)s from %(start)s to %(end)s has been cancelled.")
                % {
                    "title": booking.property.title,
                    "start": booking.start_date,
                    "end": booking.end_date,
                }
            ),
        )
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def review(self, request: Request, pk: str | None = None) -> Response:
        """
        Leave a review for this booking. ``IsBookingTenant`` already restricts this to the
        booking's own tenant; Review.clean() enforces status == PAID and the 90-day window.

        The ``hasattr`` check below is check-then-act, not a lock: ``Review.booking`` is a
        ``OneToOneField(primary_key=True)``, so two near-simultaneous submits (double-click,
        client retry-on-timeout) can both pass the check before either commits, and the second
        ``.save()`` then raises IntegrityError on the duplicate PK instead of ValidationError -
        caught separately below rather than by Review.clean(), since it never runs.
        """
        booking = self.get_object()
        if hasattr(booking, "review"):
            return Response(
                {"detail": _("This booking has already been reviewed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(booking=booking)
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        except IntegrityError:
            return Response(
                {"detail": _("This booking has already been reviewed.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
