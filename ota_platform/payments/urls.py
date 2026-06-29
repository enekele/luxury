from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path('start/', views.start_payment, name='start'),
    path('callback/', views.payment_callback, name='payment_callback'),
    path('webhook/', views.webhook, name='webhook'),
]