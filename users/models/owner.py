from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class OwnerProfile(models.Model):
    """Role-specific profile for landlords (property owners)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="owner_profile",
    )
    tax_id = models.CharField(
        _("tax ID / INN"),
        max_length=32,
        help_text=_("Used for tax reporting (Germany) / legal entities."),
    )

    bio = models.TextField(
        _("bio"),
        blank=True,
        help_text=_("Public description shown on the owner's listing page."),
    )

    is_company = models.BooleanField(
        _("is company"),
        default=False,
        help_text=_("Whether the owner is a legal entity rather than a private individual."),
    )
    company_name = models.CharField(_("company name"), max_length=255, blank=True)
    registration_number = models.CharField(
        _("registration number"),
        max_length=64,
        blank=True,
        help_text=_("Commercial register number (Handelsregisternummer), if applicable."),
    )

    languages = models.CharField(
        _("languages"),
        max_length=255,
        blank=True,
        help_text=_("Comma-separated list of languages spoken by the owner, e.g. German, English."),
    )

    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_("Whether a moderator has verified the owner's documents."),
    )
    verified_at = models.DateTimeField(_("verified at"), null=True, blank=True)
    verification_document = models.FileField(
        _("verification document"),
        upload_to="verification/owners/",
        blank=True,
        null=True,
    )

    class StatusChoices(models.TextChoices):
        ACTIVE = "active", _("Active")
        DISABLED = "disabled", _("Disabled by User")
        BANNED = "banned", _("Banned by Admin")

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE,
    )

    class Meta:
        verbose_name = _("owner profile")
        verbose_name_plural = _("owner profiles")

    def __str__(self) -> str:
        """
        :return: the linked user's email, labeled as an owner profile.
        """
        return f"{self.user.email} (owner)"
