from django.contrib import admin
from django.db.models import Count, QuerySet
from django.utils.translation import gettext_lazy as _

from .models import (
    Address,
    Amenity,
    Category,
    ModerationLog,
    PostalCode,
    Property,
    PropertyDeletionLog,
    PropertyImage,
    PropertyLocation,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(PostalCode)
class PostalCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "city", "state"]
    search_fields = ["code", "city"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["street", "house_number", "postal_code"]
    search_fields = ["street", "postal_code__code", "postal_code__city"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("postal_code")


class PropertyLocationInline(admin.StackedInline):
    model = PropertyLocation
    can_delete = False


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0
    readonly_fields = ["is_flagged"]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "owner",
        "category",
        "rent_type",
        "price_per_day",
        "price_per_month",
        "is_active",
        "moderation_status",
        "listed_as",
        "views_count",
        "created_at",
    ]
    list_filter = [
        "rent_type",
        "is_active",
        "moderation_status",
        "category",
        "listed_as",
        "created_at",
    ]
    search_fields = ["title", "description", "owner__email"]
    inlines = [PropertyLocationInline, PropertyImageInline]

    def get_queryset(self, request) -> QuerySet:
        return (
            super()
            .get_queryset(request)
            .select_related("owner", "category")
            .annotate(views_count=Count("views"))
        )

    @admin.display(description=_("views"), ordering="views_count")
    def views_count(self, obj: Property) -> int:
        """:return: total logged PropertyView count for this listing, from the annotated queryset."""
        return obj.views_count


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ["property", "source", "decision", "reviewed_by", "created_at"]
    list_filter = ["source", "decision"]
    search_fields = ["property__title"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("property", "reviewed_by")


@admin.register(PropertyDeletionLog)
class PropertyDeletionLogAdmin(admin.ModelAdmin):
    list_display = [
        "property_title",
        "property_id",
        "deleted_by",
        "ip_address",
        "deleted_at",
    ]
    search_fields = ["property_title", "deleted_by__email"]
    readonly_fields = [
        "property_id",
        "property_title",
        "deleted_by",
        "ip_address",
        "deleted_at",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("deleted_by")

    def has_add_permission(self, request) -> bool:
        """:return: False - entries are only ever created by PropertyViewSet.destroy(), never manually."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """:return: False - an audit trail must not be editable after the fact."""
        return False
