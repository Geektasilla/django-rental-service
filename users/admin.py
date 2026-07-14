from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import AgentProfile, OwnerProfile, TenantProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for the custom email-based User; is_support/is_moderator are only settable here."""

    ordering = ["email"]
    list_display = [
        "email", "first_name", "last_name", "phone",
        "is_owner", "is_agent", "is_support", "is_moderator", "is_staff",
    ]
    list_filter = ["is_owner", "is_agent", "is_support", "is_moderator", "is_staff", "is_active"]
    search_fields = ["email", "phone"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "gender")}),
        (_("Roles"), {"fields": ("is_owner", "is_agent", "is_support", "is_moderator")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "phone", "password", "password2"), # Добавлены first_name и last_name
        }),
    )


class UserNameMixin:
    """Adds first_name/last_name columns pulled from the related User."""

    @admin.display(description=_("First name"), ordering="user__first_name")
    def first_name(self, obj) -> str:
        return obj.user.first_name

    @admin.display(description=_("Last name"), ordering="user__last_name")
    def last_name(self, obj) -> str:
        return obj.user.last_name

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(TenantProfile)
class TenantProfileAdmin(UserNameMixin, admin.ModelAdmin):
    list_display = ["user", "first_name", "last_name", "status"]
    list_filter = ["status"]
    search_fields = ["user__email"]


@admin.register(OwnerProfile)
class OwnerProfileAdmin(UserNameMixin, admin.ModelAdmin):
    list_display = ["user", "first_name", "last_name", "company_name", "is_company", "is_verified", "status"]
    list_filter = ["is_company", "is_verified", "status"]
    search_fields = ["user__email", "company_name", "tax_id"]


@admin.register(AgentProfile)
class AgentProfileAdmin(UserNameMixin, admin.ModelAdmin):
    list_display = ["user", "first_name", "last_name", "company_name", "is_certified", "status"]
    list_filter = ["is_certified", "status"]
    search_fields = ["user__email", "company_name", "license_number"]