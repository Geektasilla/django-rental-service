from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import ProfileStatusChoices


class TenantProfile(models.Model):
    """Role-specific profile for tenants (renters)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="tenant_profile",
    )
    passport_data = models.CharField(
        _("passport data"),
        max_length=255,
        help_text=_("Sensitive identity document data; store encrypted or masked."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ProfileStatusChoices.choices,
        default=ProfileStatusChoices.ACTIVE,
    )

    class Meta:
        verbose_name = _("tenant profile")
        verbose_name_plural = _("tenant profiles")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=ProfileStatusChoices.values),
                name="tenant_profile_status_valid",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the linked user's email, labeled as a tenant profile.
        """
        return f"{self.user.email} (tenant)"
