from django.urls import path
from . import views

app_name = "partners_dashboard"

urlpatterns = [
    path('partners/', views.partners_dashboard, name='partners_dashboard'),
    path('toggle-availability/', views.toggle_availability, name='toggle_availability'),
    path('confirm-reservation/', views.confirm_reservation, name='confirm_reservation'),
    # ... other affiliate urls ...
]