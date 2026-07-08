from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["property", "tenant", "start_date", "end_date", "status", "price_frozen", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["property__title", "tenant__email"]
    readonly_fields = ["price_frozen"]
