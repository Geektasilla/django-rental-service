from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.utils import as_drf_validation_error
from common.validators import no_html_tags_validator
from listings.models import (
    Address,
    Amenity,
    Category,
    PostalCode,
    Property,
    PropertyImage,
    PropertyLocation,
)


class PostalCodeSerializer(serializers.ModelSerializer):
    """Read-only nested representation of a PostalCode, used inside PropertyLocationReadSerializer."""

    class Meta:
        model = PostalCode
        fields = ["code", "city", "state"]


def _is_authenticated(serializer: serializers.Serializer) -> bool:
    """
    :param serializer: a serializer instance with the standard DRF ``request`` in its context.
    :return: True if the current request comes from a logged-in user, False for a guest.
    """
    request = serializer.context.get("request")
    return bool(request and request.user and request.user.is_authenticated)


class AddressSerializer(serializers.ModelSerializer):
    """Read-only nested representation of an Address, used inside PropertyLocationReadSerializer."""

    postal_code = PostalCodeSerializer()

    class Meta:
        model = Address
        fields = ["id", "postal_code", "street", "house_number"]

    def to_representation(self, instance: Address) -> dict:
        """
        :param instance: the Address being serialized.
        :return: the standard representation; ``street``/``house_number`` are stripped for
            guests (no account) - an unregistered visitor sees only the city/postal code
            (via the nested ``postal_code``), the exact building only once they're logged in.
        """
        data = super().to_representation(instance)
        if not _is_authenticated(self):
            data.pop("street", None)
            data.pop("house_number", None)
        return data


class PropertyLocationReadSerializer(serializers.ModelSerializer):
    """Read-only nested output for Property.location, exposing the full 3NF address chain."""

    address = AddressSerializer()

    class Meta:
        model = PropertyLocation
        fields = ["address", "apartment_number", "floor_info"]

    def to_representation(self, instance: PropertyLocation) -> dict:
        """
        :param instance: the PropertyLocation being serialized.
        :return: the standard representation; ``apartment_number``/``floor_info`` are stripped
            for guests, same reasoning as AddressSerializer.street/house_number.
        """
        data = super().to_representation(instance)
        if not _is_authenticated(self):
            data.pop("apartment_number", None)
            data.pop("floor_info", None)
        return data


class PropertyLocationWriteSerializer(serializers.Serializer):
    """
    Flat write-only input for the 3NF address chain (PostalCode -> Address -> PropertyLocation).

    PropertySerializer.create()/update() resolves this into get_or_create() calls so that
    re-entering the same building's address from different listings doesn't create duplicates.
    """

    postal_code = serializers.CharField(max_length=10)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    street = serializers.CharField(max_length=255)
    house_number = serializers.CharField(max_length=20)
    apartment_number = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    floor_info = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )


class ModerationDecisionSerializer(serializers.Serializer):
    """Write-only input for PropertyViewSet.moderate() - a human moderator's approve/reject call."""

    decision = serializers.ChoiceField(
        choices=[
            Property.ModerationStatusChoices.APPROVED,
            Property.ModerationStatusChoices.REJECTED,
        ]
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class PropertyImageSerializer(serializers.ModelSerializer):
    """Read/write representation of a single PropertyImage."""

    class Meta:
        model = PropertyImage
        fields = ["id", "image"]


class CategorySerializer(serializers.ModelSerializer):
    """Read-only nested representation of a Category, used inside PropertySerializer.category_detail."""

    class Meta:
        model = Category
        fields = ["id", "name"]


class AmenitySerializer(serializers.ModelSerializer):
    """Read-only nested representation of an Amenity, used inside PropertySerializer.amenities_detail."""

    class Meta:
        model = Amenity
        fields = ["id", "name"]


class PropertySerializer(serializers.ModelSerializer):
    """
    Full read/write representation of a Property listing.

    ``owner`` and ``moderation_status`` are server-controlled (read-only here): the owner is
    taken from the request user on create, and moderation is only ever changed by the automated
    pipeline (listings/signals.py) or a future human-moderator endpoint, never by the listing's
    own owner/agent directly.
    """

    title = serializers.CharField(max_length=255, validators=[no_html_tags_validator])
    description = serializers.CharField(validators=[no_html_tags_validator])
    location = PropertyLocationWriteSerializer(write_only=True)
    location_detail = PropertyLocationReadSerializer(source="location", read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    amenities = serializers.PrimaryKeyRelatedField(
        queryset=Amenity.objects.all(), many=True, required=False, write_only=True
    )
    amenities_detail = AmenitySerializer(source="amenities", many=True, read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), write_only=True
    )
    category_detail = CategorySerializer(source="category", read_only=True)
    popularity = serializers.IntegerField(read_only=True)
    pricing = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = Property
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "category",
            "category_detail",
            "amenities",
            "amenities_detail",
            "rent_type",
            "price_per_day",
            "price_per_month",
            "pricing",
            "rooms_count",
            "is_active",
            "moderation_status",
            "listed_as",
            "power_of_attorney_document",
            "location",
            "location_detail",
            "images",
            "popularity",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "moderation_status",
            "created_at",
            "updated_at",

        ]
        extra_kwargs = {
            "price_per_day": {"write_only": True},
            "price_per_month": {"write_only": True},
        }

    def get_pricing(self, instance: Property) -> dict:
        """
        :param instance: the Property being serialized.
        :return: a single, always-present pricing object instead of two mutually-exclusive
            nullable fields (price_per_day/price_per_month - exactly one is set per rent_type,
            enforced by Property.clean()). Avoids null-noise in the response without hiding
            keys, and is self-documenting - the shape never changes based on rent_type.
            ``amount`` is stringified explicitly (matching DecimalField.to_representation()'s own
            default) since a raw Decimal returned from a SerializerMethodField would otherwise
            fall through to DRF's JSON encoder, which coerces it to float - lossy for money.
        """
        if instance.rent_type == Property.RentTypeChoices.DAILY:
            return {"period": "day", "amount": str(instance.price_per_day)}
        return {"period": "month", "amount": str(instance.price_per_month)}

    def to_representation(self, instance: Property) -> dict:
        """
        :param instance: the Property being serialized.
        :return: the standard representation, with ``owner``, ``power_of_attorney_document``,
            ``is_active`` and ``moderation_status`` stripped for everyone except the listing's
            own owner and staff/moderators. The raw owner ID has no public use (there's no
            public user-lookup endpoint to resolve it against) and only helps a scraper build a
            per-user profile across listings; the document is a real legal file (name, ID data,
            signature) tied to the agent's client; the two status fields are internal workflow
            state for the owner's dashboard and the moderation queue. All four stay
            writable/settable server-side as before - this only affects what's read back.
        """
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_view_owner_fields = bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.is_moderator or instance.owner_id == user.id)
        )
        if not can_view_owner_fields:
            data.pop("owner", None)
            data.pop("power_of_attorney_document", None)
            data.pop("is_active", None)
            data.pop("moderation_status", None)
        return data

    def create(self, validated_data: dict) -> Property:
        """
        :param validated_data: validated input, including the nested ``location`` payload.
        :return: the newly created Property, with its PropertyLocation chain resolved/created.
        :raises rest_framework.exceptions.ValidationError: if Property.clean() rejects the
            owner/listed_as/price combination (see Property.clean() for the business rules).
        """
        location_data = validated_data.pop("location")
        amenities = validated_data.pop("amenities", [])
        try:
            property_obj = Property.objects.create(
                owner=self.context["request"].user, **validated_data
            )
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        if amenities:
            property_obj.amenities.set(amenities)
        self._save_location(property_obj, location_data)
        return property_obj

    def update(self, instance: Property, validated_data: dict) -> Property:
        """
        :param instance: the Property being updated.
        :param validated_data: validated input; ``location``/``amenities`` are optional under
            partial updates (PATCH) and left untouched when omitted.
        :return: the updated Property.
        :raises rest_framework.exceptions.ValidationError: if Property.clean() rejects the result.
        """
        location_data = validated_data.pop("location", None)
        amenities = validated_data.pop("amenities", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.save()
        except DjangoValidationError as exc:
            raise as_drf_validation_error(exc)
        if amenities is not None:
            instance.amenities.set(amenities)
        if location_data is not None:
            self._save_location(instance, location_data)
        return instance

    @staticmethod
    def _save_location(property_obj: Property, location_data: dict) -> None:
        """
        Resolve the flat address input into the 3NF chain, reusing existing rows where possible.

        :param property_obj: the Property to attach/update the location for.
        :param location_data: validated PropertyLocationWriteSerializer data.
        """
        postal_code, _created = PostalCode.objects.get_or_create(
            code=location_data["postal_code"],
            defaults={"city": location_data["city"], "state": location_data["state"]},
        )
        address, _created = Address.objects.get_or_create(
            postal_code=postal_code,
            street=location_data["street"],
            house_number=location_data["house_number"],
        )
        PropertyLocation.objects.update_or_create(
            property=property_obj,
            defaults={
                "address": address,
                "apartment_number": location_data.get("apartment_number", ""),
                "floor_info": location_data.get("floor_info", ""),
            },
        )
