from django.db.models.signals import post_save
from django.dispatch import receiver

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


@receiver(post_save, sender=Property)
def moderate_property_text(sender, instance: Property, **kwargs) -> None:
    """
    Check a Property's title/description on every save and auto-reject it if flagged.
    Never auto-approves; a clean result just leaves the existing moderation_status alone.

    :param sender: the Property model class.
    :param instance: the saved Property instance.
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


@receiver(post_save, sender=PropertyImage)
def moderate_property_image(sender, instance: PropertyImage, created: bool, **kwargs) -> None:
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
        Property.objects.filter(pk=instance.property_id).update(
            moderation_status=Property.ModerationStatusChoices.REJECTED,
        )
