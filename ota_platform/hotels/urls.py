from django.urls import path
from . import views

app_name = 'hotels'

urlpatterns = [
    path('', views.hotel_list, name='hotel_list'),
    path('search/', views.hotel_search, name='hotel_search'),
    path('<int:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    path('<int:hotel_id>/availability/', views.check_availability, name='check_availability'),
    path('<int:hotel_id>/wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
]