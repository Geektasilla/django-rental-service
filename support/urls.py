from rest_framework.routers import DefaultRouter

from support.views import TicketViewSet

app_name = "support"

router = DefaultRouter()
router.register(r"", TicketViewSet, basename="ticket")

urlpatterns = router.urls
