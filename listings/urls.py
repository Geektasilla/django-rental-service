from rest_framework.routers import DefaultRouter
from listings.views import AmenityViewSet, CategoryViewSet, PropertyViewSet

app_name = "listings"

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"amenities", AmenityViewSet, basename="amenity")
router.register(r"", PropertyViewSet, basename="property")

urlpatterns = router.urls
