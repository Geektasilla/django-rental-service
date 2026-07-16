from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .property import Property


class ModerationLog(models.Model):
    """Audit trail entry for an automated or human content-moderation check on a Property."""

    class SourceChoices(models.TextChoices):
        TEXT = "text", _("Text (OpenAI Moderation API)")
        IMAGE = "image", _("Image (AWS Rekognition)")
        MANUAL = "manual", _("Manual review")

    class DecisionChoices(models.TextChoices):
        CLEAN = "clean", _("Clean")
        FLAGGED = "flagged", _("Flagged")
        ERROR = "error", _("Check failed")

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="moderation_logs",
    )
    source = models.CharField(_("source"), max_length=20, choices=SourceChoices.choices)
    decision = models.CharField(
        _("decision"), max_length=20, choices=DecisionChoices.choices
    )
    reason = models.TextField(
        _("reason"),
        blank=True,
        help_text=_("Human-readable summary of flagged categories."),
    )
    raw_response = models.JSONField(
        _("raw response"),
        null=True,
        blank=True,
        help_text=_("Raw API response, kept for audit purposes."),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_reviews",
        help_text=_("Set when a human moderator made or overrode the decision."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("moderation log")
        verbose_name_plural = _("moderation logs")
        ordering = ["-created_at"]
        constraints = [
            # Hardcoded, not SourceChoices/DecisionChoices.values: nested TextChoices isn't
            # visible from a sibling nested Meta class.
            models.CheckConstraint(
                condition=models.Q(source__in=["text", "image", "manual"]),
                name="moderationlog_source_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(decision__in=["clean", "flagged", "error"]),
                name="moderationlog_decision_valid",
            ),
        ]

    def __str__(self) -> str:
        """
        :return: the check's source and decision, e.g. "image: flagged".
        """
        return f"{self.source}: {self.decision}"
