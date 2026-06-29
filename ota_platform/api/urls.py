from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'hotels', views.HotelViewSet)
router.register(r'flights', views.FlightViewSet)
router.register(r'cars', views.CarRentalViewSet)
router.register(r'tours', views.TourViewSet)
router.register(r'bookings', views.BookingViewSet, basename='booking')
router.register(r'reviews', views.ReviewViewSet, basename='review')
router.register(r'cities', views.CityViewSet)
router.register(r'countries', views.CountryViewSet)
router.register(r'promotions', views.PromotionViewSet)
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'search', views.SearchViewSet, basename='search')
router.register(r'events', views.EventViewSet, basename='event')
router.register(r'analytics', views.AnalyticsViewSet, basename='analytics')

app_name = 'api'

urlpatterns = [
    path('v1/', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
]