from rest_framework.routers import DefaultRouter

from listings.views import PropertyViewSet

app_name = "listings"

router = DefaultRouter()
router.register(r"", PropertyViewSet, basename="property")

urlpatterns = router.urls
