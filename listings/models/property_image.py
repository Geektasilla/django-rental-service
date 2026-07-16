from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from django.conf import settings

from .property import Property


class PropertyImage(models.Model):
    """A photo attached to a Property listing."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        _("image"),
        upload_to="listings/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=settings.PROPERTY_IMAGE_ALLOWED_EXTENSIONS
            )
        ],
    )

    class Meta:
        verbose_name = _("property image")
        verbose_name_plural = _("property images")

    def __str__(self) -> str:
        """
        :return: the property title this image belongs to.
        """
        return f"Image for {self.property.title}"

    def clean(self) -> None:
        """
        Enforce the settings.MAX_PROPERTY_IMAGES limit on the parent property.

        :raises ValidationError: if the property already has the maximum number of images
            (the current instance itself is excluded from the count, so updates aren't blocked).
        """
        if self.property_id is None:
            return
        existing_count = (
            PropertyImage.objects.filter(property_id=self.property_id)
            .exclude(pk=self.pk)
            .count()
        )
        if existing_count >= settings.MAX_PROPERTY_IMAGES:
            raise ValidationError(
                _("A property cannot have more than %(max)d images.")
                % {"max": settings.MAX_PROPERTY_IMAGES}
            )

    def save(self, *args, **kwargs) -> None:
        """Run full model validation (including the image-count limit) before every save."""
        self.full_clean()
        super().save(*args, **kwargs)
