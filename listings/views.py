from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Count, ProtectedError, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from analytics.models import PropertyView, SearchHistory
from common.mixins import ActionPermissionsMixin
from common.utils import as_drf_validation_error, get_client_ip
from listings.filters import PropertyFilter
from listings.models import (
    Amenity,
    Category,
    ModerationLog,
    Property,
    PropertyDeletionLog,
    PropertyImage,
)
from listings.permissions import IsPropertyOwner
from listings.serializers import (
    AmenitySerializer,
    CategorySerializer,
    ModerationDecisionSerializer,
    PropertyImageSerializer,
    PropertySerializer,
)
from reviews.models import Review
from reviews.serializers import ReviewSerializer
from users.permissions import IsModerator, IsOwnerOrAgent

_MODIFY_ACTIONS = [
    "update",
    "partial_update",
    "destroy",
    "upload_image",
    "delete_image",
]


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only taxonomy list, so a client can populate a category dropdown when creating a listing."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None


class AmenityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only taxonomy list, so a client can populate an amenities checklist when creating a listing."""

    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [AllowAny]
    pagination_class = None


class PropertyViewSet(ActionPermissionsMixin, viewsets.ModelViewSet):
    """
    CRUD + search/filter/sort for Property listings.

    Visibility (see tools/roles_permissions_overview.md): guests and other users only ever see
    APPROVED + is_active listings; an owner/agent additionally sees their own listings regardless
    of moderation/active status; staff/moderators see everything.
    """

    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PropertyFilter
    search_fields = ["title", "description"]
    ordering_fields = ["price_per_day", "price_per_month", "created_at", "popularity"]
    ordering = ["-created_at"]
    # AllowAny for read actions (guest browsing), IsOwnerOrAgent for creation, and both
    # IsOwnerOrAgent + IsPropertyOwner (object-level) for anything that mutates an existing listing.
    default_permission_classes = [AllowAny]
    permission_classes_by_action = {
        "create": [IsOwnerOrAgent],
        "moderate": [IsModerator],
        **{action: [IsOwnerOrAgent, IsPropertyOwner] for action in _MODIFY_ACTIONS},
    }

    def get_queryset(self) -> QuerySet:
        """
        :return: the Property queryset for the current user, pre-joined against owner/category/
            location/address/postal_code and prefetched for images/amenities to avoid N+1 queries,
            annotated with a ``popularity`` count (distinct views + distinct reviews).
        """
        queryset = (
            Property.objects.select_related(
                "owner", "category", "location__address__postal_code"
            )
            .prefetch_related("images", "amenities")
            .annotate(
                popularity=Count("views", distinct=True)
                + Count("bookings__review", distinct=True)
            )
        )
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_moderator):
            return queryset
        visible = Q(
            is_active=True, moderation_status=Property.ModerationStatusChoices.APPROVED
        )
        if user.is_authenticated:
            visible |= Q(owner=user)
        return queryset.filter(visible).distinct()

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        Log a SearchHistory entry whenever a text search is performed, including for guests
        (user=None), before delegating to the standard list behaviour.
        """
        search_query = request.query_params.get("search")
        if search_query:
            SearchHistory.objects.create(
                user=request.user if request.user.is_authenticated else None,
                search_query=search_query,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Log a PropertyView entry for every listing detail view, including guests."""
        instance = self.get_object()
        PropertyView.objects.create(
            property=instance,
            user=request.user if request.user.is_authenticated else None,
            ip_address=get_client_ip(request),
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """
        :return: 204 on success; 409 if the listing has protected history (e.g. Booking rows,
            Booking.property is on_delete=PROTECT) and can't be deleted.
        """
        instance = self.get_object()
        property_id, property_title = instance.pk, instance.title
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": _(
                        "This listing has bookings or other history and cannot be deleted. "
                        "Use is_active to unpublish it instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        PropertyDeletionLog.objects.create(
            property_id=property_id,
            property_title=property_title,
            deleted_by=request.user,
            ip_address=get_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser],
        url_path="images",
    )
    def upload_image(self, request: Request, pk: str | None = None) -> Response:
        """
        Add a photo to this listing (subject to Property/PropertyImage validation, e.g. MAX_PROPERTY_IMAGES).

        ``PropertyImage.clean()``'s image-count check is check-then-act, same shape as the review
        race fixed in bookings/views.py::review(): two near-simultaneous uploads at the limit can
        both pass the Python-side count before either commits, so the second INSERT is caught by
        the DB-level ``property_image_limit_check`` trigger (listings/migrations/
        0007_property_image_limit_trigger.py) instead, raising IntegrityError rather than
        ValidationError - caught separately below for the same clean 400 instead of a 500.
        """
        property_obj = self.get_object()
        serializer = PropertyImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(property=property_obj)
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        except IntegrityError:
            return Response(
                {
                    "detail": _(
                        "A property cannot have more than the maximum number of images."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(
        self, request: Request, pk: str | None = None, image_id: str | None = None
    ) -> Response:
        """Remove one photo from this listing."""
        property_obj = self.get_object()
        image = get_object_or_404(PropertyImage, pk=image_id, property=property_obj)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def moderate(self, request: Request, pk: str | None = None) -> Response:
        """
        Human moderator approve/reject action - the only way a listing can reach APPROVED, since
        the automated pipeline (listings/signals.py) is only ever allowed to REJECT, never approve.
        """
        property_obj = self.get_object()
        serializer = ModerationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        reason = serializer.validated_data["reason"]

        property_obj.moderation_status = decision
        try:
            property_obj.save()
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)

        ModerationLog.objects.create(
            property=property_obj,
            source=ModerationLog.SourceChoices.MANUAL,
            decision=(
                ModerationLog.DecisionChoices.CLEAN
                if decision == Property.ModerationStatusChoices.APPROVED
                else ModerationLog.DecisionChoices.FLAGGED
            ),
            reason=reason,
            reviewed_by=request.user,
        )
        return Response(self.get_serializer(property_obj).data)

    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request: Request, pk: str | None = None) -> Response:
        """Public list of all reviews for this listing - falls through get_permissions() to AllowAny."""
        property_obj = self.get_object()
        queryset = (
            Review.objects.filter(booking__property=property_obj)
            .select_related("booking__tenant")
            .order_by("-created_at")
        )
        page = self.paginate_queryset(queryset)
        serializer = ReviewSerializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
