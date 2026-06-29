from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('bookings/', views.bookings, name='user_bookings'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('add-to-wishlist/', views.add_to_wishlist, name='add_to_wishlist'),
    path('remove-from-wishlist/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('loyalty-points/', views.loyalty_points, name='loyalty_points'),
    path('referrals/', views.referrals, name='referrals'),
    path('subscriptions/', views.subscription_packages, name='subscription_packages'),
    path('activity-log/', views.activity_log, name='activity_log'),
    path('public/<int:user_id>/', views.public_profile, name='public_profile'),
]