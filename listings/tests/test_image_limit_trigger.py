import io

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from PIL import Image

from common.tests.factories import make_owner, make_property
from listings.models import PropertyImage


def _fake_image_file(name: str = "photo.jpg") -> SimpleUploadedFile:
    """:return: a minimal valid 1x1 JPEG, small enough to upload quickly in tests."""
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/jpeg")


class ImageLimitTriggerTests(TestCase):
    """
    PropertyImage.clean()'s MAX_PROPERTY_IMAGES check is check-then-act (see
    listings/views.py::upload_image docstring) - the DB trigger (listings/migrations/
    0007_property_image_limit_trigger.py) is the backstop that bulk_create() can't bypass.

    The trigger's threshold (10) is hardcoded in SQL, not read from settings.MAX_PROPERTY_IMAGES
    (see the migration's docstring) - so this test creates 10 real images rather than overriding
    the setting, to actually exercise the value the trigger enforces.
    """

    def setUp(self) -> None:
        self.owner = make_owner()
        self.property = make_property(self.owner)
        for i in range(10):
            PropertyImage.objects.create(property=self.property, image=_fake_image_file(f"{i}.jpg"))

    def test_clean_blocks_the_11th_image_through_normal_save(self) -> None:
        with self.assertRaises(Exception):
            PropertyImage.objects.create(property=self.property, image=_fake_image_file("11th.jpg"))

    def test_trigger_blocks_the_11th_image_bypassing_clean_via_bulk_create(self) -> None:
        eleventh_image = PropertyImage(property=self.property, image=_fake_image_file("11th.jpg"))
        with self.assertRaises(IntegrityError):
            PropertyImage.objects.bulk_create([eleventh_image])


class MaxPropertyImagesCanaryTest(TestCase):
    """
    Not a behavior test - a tripwire. settings.MAX_PROPERTY_IMAGES must stay in sync with the
    hardcoded 10 in listings/migrations/0007_property_image_limit_trigger.py (the trigger can't
    read Python settings). If this fails, someone changed one without the other.
    """

    def test_max_property_images_matches_the_hardcoded_db_trigger_threshold(self) -> None:
        self.assertEqual(
            settings.MAX_PROPERTY_IMAGES,
            10,
            "MAX_PROPERTY_IMAGES changed - update the hardcoded threshold in "
            "listings/migrations/0007_property_image_limit_trigger.py to match, then update this test.",
        )
