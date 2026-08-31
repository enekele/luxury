from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search, name='search'),
    path('destinations/', views.destinations, name='destinations'),
    path('destinations/<str:country_code>/', views.destination_detail, name='destination_detail'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service, name='terms_of_service'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('concierge/', views.concierge, name='concierge'),
    
    # AJAX endpoints
    path('ajax/cities/', views.ajax_get_cities, name='ajax_get_cities'),
    path('ajax/check-promotion/', views.ajax_check_promotion, name='ajax_check_promotion'),
    path('ajax/travel-assistant/', views.travel_assistant, name='travel_assistant'),
    path('ajax/visa-copilot/', views.visa_copilot, name='visa_copilot'),
    path('ajax/compliance-check/', views.compliance_check, name='compliance_check'),
    path('ajax/concierge/', views.concierge_chat, name='concierge_chat'),
    path('ajax/concierge-book/', views.concierge_book, name='concierge_book'),
]
