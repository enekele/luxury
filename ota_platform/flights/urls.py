from django.urls import path
from . import views

app_name = 'flights'

urlpatterns = [
    path('', views.flight_list, name='flight_list'),
    path('search/', views.flight_search, name='flight_search'),
]