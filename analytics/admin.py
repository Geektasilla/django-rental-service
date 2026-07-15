from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import PropertyView, SearchHistory

POPULAR_PROPERTIES_LIMIT = 10
POPULAR_SEARCHES_LIMIT = 10


class UserDisplayMixin:
    """Shared "user or Anonymous Guest" column for admin models with a nullable ``user`` FK."""

    @admin.display(description=_("user"), ordering="user__email")
    def user_display(self, obj) -> str:
        """:return: the user's email, or a readable placeholder for anonymous guests."""
        return obj.user.email if obj.user else _("Anonymous Guest")


@admin.register(SearchHistory)
class SearchHistoryAdmin(UserDisplayMixin, admin.ModelAdmin):
    list_display = ["search_query", "user_display", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["search_query", "user__email"]
    change_list_template = "admin/analytics/searchhistory/change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def changelist_view(self, request, extra_context=None):
        """Inject a "most popular searches" summary table above the raw log list."""
        extra_context = extra_context or {}
        extra_context["popular_searches"] = (
            SearchHistory.objects.values("search_query")
            .annotate(total_searches=Count("id"))
            .order_by("-total_searches")[:POPULAR_SEARCHES_LIMIT]
        )
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(PropertyView)
class PropertyViewAdmin(UserDisplayMixin, admin.ModelAdmin):
    list_display = ["property", "user_display", "ip_address", "viewed_at"]
    list_filter = ["viewed_at"]
    search_fields = ["property__title", "user__email", "ip_address"]
    change_list_template = "admin/analytics/propertyview/change_list.html"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("property", "user")

    def changelist_view(self, request, extra_context=None):
        """Inject a "most viewed properties" summary table above the raw log list."""
        extra_context = extra_context or {}
        extra_context["popular_properties"] = (
            PropertyView.objects.values("property__title")
            .annotate(total_views=Count("id"))
            .order_by("-total_views")[:POPULAR_PROPERTIES_LIMIT]
        )
        return super().changelist_view(request, extra_context=extra_context)
