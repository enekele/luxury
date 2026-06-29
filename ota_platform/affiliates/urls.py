from django.urls import path
from . import views

app_name = 'affiliates'

urlpatterns = [
    # Affiliate Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.affiliate_profile, name='profile'),
    path('kyc/', views.kyc_verification, name='kyc_verification'),
    
    # Earnings & Commissions
    path('earnings/', views.earnings, name='earnings'),
    
    # Promo Codes
    path('promo-codes/', views.promo_codes, name='promo_codes'),
    path('promo-codes/create/', views.create_promo_code, name='create_promo_code'),
    
    # Marketing
    path('marketing-resources/', views.marketing_resources, name='marketing_resources'),
    path('marketing-resources/<int:resource_id>/download/', views.download_resource, name='download_resource'),
    
    # Referral Tracking
    path('referrals/', views.referral_tracking, name='referral_tracking'),
    
    # Authentication
    path('signup/', views.affiliate_signup, name='signup'),
    path('login/', views.affiliate_login, name='login'),
    
    # Tracking
    path('track/', views.track_affiliate_click, name='track_click'),

   
]