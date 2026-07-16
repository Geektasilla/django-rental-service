"""
URL configuration for django_rental_service project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from common.views import HealthCheckView

# Interface
admin.site.site_header = 'Django Rental Service Admin'
admin.site.site_title = 'Django Rental Service'
admin.site.index_title = _('Administration')

urlpatterns = [
    # SYSTEM
    path('', RedirectView.as_view(url='api/schema/swagger-ui/', permanent=False)),
    path('admin/', admin.site.urls),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('i18n/', include('django.conf.urls.i18n')),

    # BUSINESS API
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/users/', include('users.profile_urls')),
    path('api/v1/listings/', include('listings.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/notifications/', include('notifications.urls')),
    path('api/v1/support/', include('support.urls')),
    path('api/v1/analytics/', include('analytics.urls')),

    # API documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
