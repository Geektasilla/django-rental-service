from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from notifications.models import Notification
from users.models import User

from .models import ModerationLog, Property, PropertyImage
from .services.moderation import moderate_image, moderate_text


def _decision_for(result: dict) -> str:
    """
    Map a moderation service result to a ModerationLog decision value.

    :param result: dict returned by moderate_text/moderate_image.
    :return: one of ModerationLog.DecisionChoices.
    """
    if result["error"]:
        return ModerationLog.DecisionChoices.ERROR
    if result["flagged"]:
        return ModerationLog.DecisionChoices.FLAGGED
    return ModerationLog.DecisionChoices.CLEAN


def _notify_moderators_of_pending_listing(instance: Property) -> None:
    """
    Create an in-app Notification for every active moderator when a new listing needs review.

    In-app only (Notification row, no email/push) - moderators must check GET
    /api/v1/notifications/ themselves; there is no external ping.

    :param instance: the newly created Property, still PENDING after the automated text check.
    """
    moderators = User.objects.filter(is_moderator=True, is_active=True)
    Notification.objects.bulk_create(
        (
            Notification(
                user=moderator,
                message=str(
                    _("New listing pending review: %(title)s")
                    % {"title": instance.title}
                ),
            )
            for moderator in moderators
        ),
        batch_size=500,
    )


@receiver(post_save, sender=Property)
def moderate_property_text(sender, instance: Property, created: bool, **kwargs) -> None:
    """
    Check a Property's title/description on every save and auto-reject it if flagged.
    Never auto-approves; a clean result just leaves the existing moderation_status alone.

    On creation, if the listing is still PENDING after this check, notify moderators - not on
    later edits, to avoid re-notifying on every unrelated update to an already-reviewed listing.

    :param sender: the Property model class.
    :param instance: the saved Property instance.
    :param created: True only for the initial insert.
    """
    result = moderate_text(f"{instance.title}\n{instance.description}")
    ModerationLog.objects.create(
        property=instance,
        source=ModerationLog.SourceChoices.TEXT,
        decision=_decision_for(result),
        reason=result["reason"],
        raw_response=result["raw_response"],
    )
    if result["flagged"]:
        Property.objects.filter(pk=instance.pk).update(
            moderation_status=Property.ModerationStatusChoices.REJECTED,
        )
    elif (
        created
        and instance.moderation_status == Property.ModerationStatusChoices.PENDING
    ):
        _notify_moderators_of_pending_listing(instance)


@receiver(post_save, sender=PropertyImage)
def moderate_property_image(
    sender, instance: PropertyImage, created: bool, **kwargs
) -> None:
    """
    Check a newly uploaded PropertyImage and auto-reject the parent listing if flagged.
    Only runs once per upload; never auto-approves.

    :param sender: the PropertyImage model class.
    :param instance: the saved PropertyImage instance.
    :param created: True only for the initial upload.
    """
    if not created:
        return

    result = moderate_image(instance.image)
    ModerationLog.objects.create(
        property=instance.property,
        source=ModerationLog.SourceChoices.IMAGE,
        decision=_decision_for(result),
        reason=result["reason"],
        raw_response=result["raw_response"],
    )
    if result["flagged"]:
        PropertyImage.objects.filter(pk=instance.pk).update(is_flagged=True)
        Property.objects.filter(pk=instance.property_id).update(
            moderation_status=Property.ModerationStatusChoices.REJECTED,
        )

