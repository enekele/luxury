from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel

User = get_user_model()


class AdminActivity(BaseModel):
    """Admin activity log"""
    admin_user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Admin Activities"
    
    def __str__(self):
        return f"{self.admin_user.email} - {self.action}"


class SystemSettings(BaseModel):
    """System-wide settings"""
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    max_booking_days_advance = models.IntegerField(default=365)
    min_booking_hours_advance = models.IntegerField(default=2)
    auto_confirm_bookings = models.BooleanField(default=False)
    email_notifications_enabled = models.BooleanField(default=True)
    sms_notifications_enabled = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return "System Settings"


class RevenueReport(BaseModel):
    """Revenue tracking and reporting"""
    date = models.DateField()
    service_type = models.CharField(max_length=20, choices=[
        ('hotel', 'Hotels'),
        ('flight', 'Flights'),
        ('car', 'Car Rentals'),
        ('tour', 'Tours'),
        ('event', 'Event')
    ])
    total_bookings = models.IntegerField(default=0)
    total_revenue = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    commission_earned = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    
    class Meta:
        unique_together = ('date', 'service_type')
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.service_type.title()} - {self.date}"


class PartnerCommission(BaseModel):
    """Partner commission tracking"""
    partner_name = models.CharField(max_length=200)
    partner_type = models.CharField(max_length=20, choices=[
        ('hotel', 'Hotel'),
        ('airline', 'Airline'),
        ('car_rental', 'Car Rental'),
        ('tour_operator', 'Tour Operator'),
    ])
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    total_bookings = models.IntegerField(default=0)
    total_commission = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    last_payout_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.partner_name} - {self.commission_rate}%"
    
