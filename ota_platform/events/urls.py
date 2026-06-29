from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'events'

router = DefaultRouter()
router.register(r'categories', views.EventCategoryViewSet, basename='category')
router.register(r'venues', views.EventVenueViewSet, basename='venue')
router.register(r'events', views.EventViewSet, basename='event')
router.register(r'ticket-categories', views.TicketCategoryViewSet, basename='ticket-category')
router.register(r'my-tickets', views.EventTicketViewSet, basename='my-ticket')
router.register(r'my-bookings', views.EventBookingViewSet, basename='my-booking')
router.register(r'reviews', views.EventReviewViewSet, basename='review')

urlpatterns = [
    path('api/', include(router.urls)),
    path('', views.event_list, name='event_list'),
    path('<int:event_id>/', views.event_detail, name='event_detail'),
    path('<int:event_id>/checkout/', views.event_checkout, name='event_checkout'),
    path('booking-success/<int:booking_id>/', views.booking_success, name='booking_success'),
]
