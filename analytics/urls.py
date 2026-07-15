from django.urls import path

from analytics.views import PopularSearchesView

app_name = "analytics"

urlpatterns = [
    path("popular-searches/", PopularSearchesView.as_view(), name="popular-searches"),
]
