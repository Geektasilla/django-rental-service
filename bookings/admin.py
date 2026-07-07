from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["property", "tenant", "start_date", "end_date", "status", "price_frozen"]
    list_filter = ["status"]
    search_fields = ["property__title", "tenant__email"]
    readonly_fields = ["price_frozen"]
