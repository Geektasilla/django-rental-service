from django.db import models
from django.utils.translation import gettext_lazy as _


class ProfileStatusChoices(models.TextChoices):
    """Soft-disable status shared by all per-role user profiles (Tenant/Owner/Agent)."""

    ACTIVE = "active", _("Active")
    DISABLED = "disabled", _("Disabled by User")
    BANNED = "banned", _("Banned by Admin")
