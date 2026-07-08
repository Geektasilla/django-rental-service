from django.contrib import admin

from .models import (
    Address,
    Amenity,
    Category,
    ModerationLog,
    PostalCode,
    Property,
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


class PropertyLocationInline(admin.StackedInline):
    model = PropertyLocation
    can_delete = False


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = [
        "title", "owner", "category", "rent_type", "price_per_day", "price_per_month",
        "is_active", "moderation_status", "listed_as", "created_at",
    ]
    list_filter = ["rent_type", "is_active", "moderation_status", "category", "listed_as", "created_at"]
    search_fields = ["title", "description", "owner__email"]
    inlines = [PropertyLocationInline, PropertyImageInline]


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ["property", "source", "decision", "reviewed_by", "created_at"]
    list_filter = ["source", "decision"]
    search_fields = ["property__title"]
