from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.users_management, name='users_management'),
    path('bookings/', views.bookings_management, name='bookings_management'),
    path('content/', views.content_management, name='content_management'),
    path('analytics/', views.analytics, name='analytics'),
    path('promotions/', views.promotions_management, name='promotions_management'),
    path('settings/', views.system_settings, name='system_settings'),
]