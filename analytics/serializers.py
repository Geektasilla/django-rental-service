from rest_framework import serializers


class PopularSearchSerializer(serializers.Serializer):
    """One aggregated row: a search query and how many times it's been logged."""

    search_query = serializers.CharField()
    count = serializers.IntegerField()
