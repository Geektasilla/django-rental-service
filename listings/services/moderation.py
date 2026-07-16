import logging

from django.conf import settings
from django.db.models.fields.files import FieldFile

logger = logging.getLogger(__name__)


def moderate_text(text: str) -> dict:
    """
    Check listing text (title + description) for prohibited content via the OpenAI Moderation API.

    :param text: the combined text to check.
    :return: dict with keys 'flagged' (bool), 'reason' (str), 'raw_response' (dict | None), 'error' (bool).
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY is not configured; skipping text moderation.")
        return {
            "flagged": False,
            "reason": "Moderation skipped: OPENAI_API_KEY not configured.",
            "raw_response": None,
            "error": True,
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.moderations.create(input=text)
        result = response.results[0]
        flagged_categories = [
            category
            for category, is_flagged in result.categories.model_dump().items()
            if is_flagged
        ]
        return {
            "flagged": result.flagged,
            "reason": ", ".join(flagged_categories),
            "raw_response": response.model_dump(),
            "error": False,
        }
    except Exception:
        logger.exception("Text moderation check failed.")
        return {
            "flagged": False,
            "reason": "Moderation check failed due to an internal error.",
            "raw_response": None,
            "error": True,
        }


def moderate_image(image_field: FieldFile) -> dict:
    """
    Check a property photo for prohibited content via AWS Rekognition's moderation-label detection.

    :param image_field: the saved ImageField file to read and scan.
    :return: dict with keys 'flagged' (bool), 'reason' (str), 'raw_response' (dict | None), 'error' (bool).
    """
    if not (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY):
        logger.warning("AWS credentials are not configured; skipping image moderation.")
        return {
            "flagged": False,
            "reason": "Moderation skipped: AWS credentials not configured.",
            "raw_response": None,
            "error": True,
        }

    try:
        import boto3

        client = boto3.client(
            "rekognition",
            region_name=settings.AWS_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

        image_field.open("rb")
        try:
            image_bytes = image_field.read()
        finally:
            image_field.close()

        response = client.detect_moderation_labels(
            Image={"Bytes": image_bytes},
            MinConfidence=60,
        )
        labels = response.get("ModerationLabels", [])
        return {
            "flagged": bool(labels),
            "reason": ", ".join(
                f"{label['Name']} ({label['Confidence']:.0f}%)" for label in labels
            ),
            "raw_response": {
                k: v for k, v in response.items() if k != "ResponseMetadata"
            },
            "error": False,
        }
    except Exception:
        logger.exception("Image moderation check failed.")
        return {
            "flagged": False,
            "reason": "Moderation check failed due to an internal error.",
            "raw_response": None,
            "error": True,
        }
