from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from django_countries.fields import CountryField

User = get_user_model()


class BaseModel(models.Model):
    """Base model with common fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True


class Currency(models.Model):
    """Currency model for multi-currency support"""
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1.0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Currencies"
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Country(models.Model):
    """Country model for location management"""
    name = models.CharField(max_length=100)
    code = CountryField()
    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, null=True)
    timezone = models.CharField(max_length=50, default='UTC')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Countries"
    
    def __str__(self):
        return self.name


class City(models.Model):
    """City model for location management"""
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "Cities"
    
    def __str__(self):
        return f"{self.name}, {self.country.name}"


class SiteSettings(models.Model):
    """Site-wide settings"""
    site_name = models.CharField(max_length=100, default="TravelHub")
    site_description = models.CharField( max_length=500, default="your best travel service")
    default_currency = models.ForeignKey(Currency, on_delete=models.SET_NULL, null=True)
    default_language = models.CharField(max_length=5, default='en')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    booking_cancellation_hours = models.IntegerField(default=24)
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return self.site_name


class Promotion(BaseModel):
    """Promotion and discount model"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    code = models.CharField(max_length=20, unique=True)
    discount_type = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    max_discount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    usage_limit = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)
    service_type = models.CharField(max_length=20, choices=[
        ('all', 'All Services'),
        ('hotel', 'Hotels'),
        ('flight', 'Flights'),
        ('car', 'Car Rentals'),
        ('tour', 'Tours'),
    ], default='all')
    
    def __str__(self):
        return self.title
    
    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return (self.valid_from <= now <= self.valid_until and 
                self.is_active and 
                (self.usage_limit is None or self.used_count < self.usage_limit))


class Newsletter(BaseModel):
    """Newsletter subscription model"""
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return self.email


class ConciergeRequest(BaseModel):
    """Personalized concierge request and booking action log."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    query = models.TextField()
    response = models.TextField(blank=True)
    intent = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    booked = models.BooleanField(default=False)
    booking_reference = models.CharField(max_length=20, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Concierge Request'
        verbose_name_plural = 'Concierge Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Concierge request #{self.id} - {self.user.email if self.user else 'Guest'}"
