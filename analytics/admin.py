from django.contrib import admin

from .models import PropertyView, SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ["search_query", "user", "created_at"]
    search_fields = ["search_query", "user__email"]


@admin.register(PropertyView)
class PropertyViewAdmin(admin.ModelAdmin):
    list_display = ["property", "user", "ip_address", "viewed_at"]
    search_fields = ["property__title", "user__email", "ip_address"]
