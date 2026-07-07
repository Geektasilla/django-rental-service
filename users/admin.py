from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import AgentProfile, OwnerProfile, TenantProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Admin for the custom email-based User; is_support/is_moderator are only settable here."""

    ordering = ["email"]
    list_display = ["email", "phone", "is_owner", "is_agent", "is_support", "is_moderator", "is_staff"]
    search_fields = ["email", "phone"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone", "avatar", "gender")}),
        (_("Roles"), {"fields": ("is_owner", "is_agent", "is_support", "is_moderator")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "phone", "password1", "password2"),
        }),
    )


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "status"]
    list_filter = ["status"]
    search_fields = ["user__email"]


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company_name", "is_company", "is_verified", "status"]
    list_filter = ["is_company", "is_verified", "status"]
    search_fields = ["user__email", "company_name", "tax_id"]


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company_name", "is_certified", "status"]
    list_filter = ["is_certified", "status"]
    search_fields = ["user__email", "company_name", "license_number"]
