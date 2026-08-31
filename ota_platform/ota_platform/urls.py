from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import health_check

urlpatterns = [
    path('healthz/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('admin-dashboard/', include('admin_dashboard.urls')),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    path('api/', include('api.urls')),
    path('', include('core.urls')),
    path('users/', include('users.urls')),
    path('hotels/', include('hotels.urls')),
    path('flights/', include('flights.urls')),
    path('cars/', include('cars.urls')),
    path('tours/', include('tours.urls')),
    path('events/', include('events.urls')),
    path('bookings/', include('bookings.urls')),
    path('payments/', include('payments.urls')),
    path('affiliates/', include('affiliates.urls')),
    path('partners/', include('partners_dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
