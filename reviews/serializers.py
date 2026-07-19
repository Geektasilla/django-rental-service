from rest_framework import serializers

from common.validators import no_html_tags_validator
from reviews.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """
    Read/write representation of a Review.

    ``booking`` is server-controlled: it's always taken from the URL (BookingViewSet.review
    action), never from the request body - a review's identity IS its booking (OneToOne PK).
    ``tenant``/``property`` are read-only conveniences so a listing's review list is self-contained.
    """

    tenant = serializers.PrimaryKeyRelatedField(source="booking.tenant", read_only=True)
    property = serializers.PrimaryKeyRelatedField(
        source="booking.property", read_only=True
    )
    comment = serializers.CharField(validators=[no_html_tags_validator])

    class Meta:
        model = Review
        fields = ["booking", "tenant", "property", "rating", "comment", "created_at"]
        read_only_fields = ["booking", "tenant", "property", "created_at"]
