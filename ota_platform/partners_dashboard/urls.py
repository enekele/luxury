from django.urls import path

from . import views


app_name = "partners_dashboard"

urlpatterns = [
    path('', views.partners_dashboard, name='partners_dashboard'),
    path('partners/', views.partners_dashboard, name='legacy_partners_dashboard'),
    path('locations/', views.manage_locations, name='manage_locations'),
    path('properties/', views.manage_properties, name='manage_properties'),
    path('properties/hotels/create/', views.create_hotel_property, name='create_hotel_property'),
    path('properties/hotels/cities/', views.cities_for_country, name='cities_for_country'),
    path('properties/flights/create/', views.create_flight_property, name='create_flight_property'),
    path('properties/cars/create/', views.create_car_property, name='create_car_property'),
    path('properties/tours/create/', views.create_tour_property, name='create_tour_property'),
    path('properties/<int:hotel_id>/update/', views.update_property, name='update_property'),
    path('properties/hotels/<int:hotel_id>/update/', views.update_hotel_property, name='update_hotel_property'),
    path('properties/flights/<int:flight_id>/update/', views.update_flight_property, name='update_flight_property'),
    path('properties/cars/<int:car_id>/update/', views.update_car_property, name='update_car_property'),
    path('properties/tours/<int:tour_id>/update/', views.update_tour_property, name='update_tour_property'),
    path('properties/hotels/<int:hotel_id>/checkout/', views.checkout_hotel_property, name='checkout_hotel_property'),
    path('properties/flights/<int:flight_id>/checkout/', views.checkout_flight_property, name='checkout_flight_property'),
    path('properties/cars/<int:car_id>/checkout/', views.checkout_car_property, name='checkout_car_property'),
    path('properties/tours/<int:tour_id>/checkout/', views.checkout_tour_property, name='checkout_tour_property'),
    path('toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('confirm-reservation/', views.confirm_reservation, name='confirm_reservation'),
]
