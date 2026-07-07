from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import ProfileStatusChoices


class AgentProfile(models.Model):
    """Role-specific profile for real estate agents."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="agent_profile",
    )
    company_name = models.CharField(_("company name"), max_length=255)
    license_number = models.CharField(_("license number"), max_length=64)
    is_certified = models.BooleanField(_("certified status"), default=False)
    website = models.URLField(_("website"), max_length=200, null=True, blank=True)
    bio = models.TextField(_("bio / specialization"), null=True, blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ProfileStatusChoices.choices,
        default=ProfileStatusChoices.ACTIVE,
    )

    class Meta:
        verbose_name = _("agent profile")
        verbose_name_plural = _("agent profiles")

    def __str__(self) -> str:
        """
        :return: the linked user's email together with their company name.
        """
        return f"{self.user.email} ({self.company_name})"
