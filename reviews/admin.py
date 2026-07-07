from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["booking", "rating", "created_at"]
    list_filter = ["rating"]
    search_fields = ["booking__property__title", "booking__tenant__email"]
