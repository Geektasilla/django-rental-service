from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "property",
        "tenant",
        "tenant_first_name",
        "tenant_last_name",
        "owner_first_name",
        "owner_last_name",
        "start_date",
        "end_date",
        "status",
        "price_frozen",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["property__title", "tenant__email"]
    readonly_fields = ["price_frozen"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("tenant", "property__owner")

    @admin.display(description=_("Tenant first name"), ordering="tenant__first_name")
    def tenant_first_name(self, obj) -> str:
        return obj.tenant.first_name

    @admin.display(description=_("Tenant last name"), ordering="tenant__last_name")
    def tenant_last_name(self, obj) -> str:
        return obj.tenant.last_name

    @admin.display(
        description=_("Owner first name"), ordering="property__owner__first_name"
    )
    def owner_first_name(self, obj) -> str:
        return obj.property.owner.first_name

    @admin.display(
        description=_("Owner last name"), ordering="property__owner__last_name"
    )
    def owner_last_name(self, obj) -> str:
        return obj.property.owner.last_name
