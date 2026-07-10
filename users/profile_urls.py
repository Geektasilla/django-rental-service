from django.urls import path

from users.views import UserProfileView

app_name = "users"

urlpatterns = [
    path("me/", UserProfileView.as_view(), name="user-profile"),
]
