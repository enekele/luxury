from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel, City
import datetime

User = get_user_model()


class Airline(BaseModel):
    """Airline model"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # IATA code
    logo = models.ImageField(upload_to='airlines/', blank=True)
    website = models.URLField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Airport(BaseModel):
    """Airport model"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, unique=True)  # IATA code
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='airports')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Flight(BaseModel):
    """Flight model"""
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE)
    flight_number = models.CharField(max_length=20)
    
    # Route
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='departing_flights')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='arriving_flights')
    
    # Schedule
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    duration = models.DurationField()
    
    # Aircraft
    aircraft_type = models.CharField(max_length=50, blank=True)
    total_seats = models.IntegerField(default=180)
    available_seats = models.IntegerField(default=180)
    
    # Pricing
    economy_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    business_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    first_class_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
        ('departed', 'Departed'),
        ('arrived', 'Arrived'),
    ], default='scheduled')
    
    # Stops
    is_direct = models.BooleanField(default=True)
    stops = models.IntegerField(default=0)
    
    # Booking settings
    cancellation_policy = models.TextField(blank=True)
    baggage_policy = models.TextField(blank=True)
    # Optional link to a Partner account
    partner_profile = models.ForeignKey(
        'partners_dashboard.Partner',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='flights',
    )
    
    class Meta:
        ordering = ['departure_time']
    
    def __str__(self):
        return f"{self.airline.code}{self.flight_number} - {self.origin.code} to {self.destination.code}"
    
    @property
    def duration_hours(self):
        return self.duration.total_seconds() / 3600
    
    @property
    def is_available(self):
        return self.available_seats > 0 and self.status == 'scheduled'

    def save(self, *args, **kwargs):
        """Ensure duration is a timedelta. If arrival/departure provided, compute duration."""
        try:
            if self.departure_time and self.arrival_time:
                # Compute duration from datetimes
                computed = self.arrival_time - self.departure_time
                if isinstance(computed, datetime.timedelta):
                    self.duration = computed
        except Exception:
            # don't block save on unexpected value types; let DB validations handle it
            pass
        super().save(*args, **kwargs)


class FlightClass(BaseModel):
    """Flight class/cabin types"""
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='classes')
    class_type = models.CharField(max_length=20, choices=[
        ('economy', 'Economy'),
        ('premium_economy', 'Premium Economy'),
        ('business', 'Business'),
        ('first', 'First Class'),
    ])
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    available_seats = models.IntegerField(default=0)
    total_seats = models.IntegerField(default=0)
    
    # Amenities
    baggage_allowance = models.CharField(max_length=50, blank=True)
    meal_service = models.BooleanField(default=False)
    wifi_included = models.BooleanField(default=False)
    seat_selection = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('flight', 'class_type')
    
    def __str__(self):
        return f"{self.flight} - {self.class_type.title()}"


class FlightSearch(models.Model):
    """Flight search history"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='search_origins')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='search_destinations')
    departure_date = models.DateField()
    return_date = models.DateField(null=True, blank=True)
    passengers = models.IntegerField(default=1)
    class_type = models.CharField(max_length=20, default='economy')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.origin.code} to {self.destination.code} - {self.departure_date}"


class FlightRoute(BaseModel):
    """Popular flight routes"""
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='route_origins')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='route_destinations')
    is_popular = models.BooleanField(default=False)
    average_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    average_duration = models.DurationField()
    
    class Meta:
        unique_together = ('origin', 'destination')
    
    def __str__(self):
        return f"{self.origin.code} → {self.destination.code}"


class FlightDeal(BaseModel):
    """Flight deals and special offers"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    route = models.ForeignKey(FlightRoute, on_delete=models.CASCADE, null=True, blank=True)
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, null=True, blank=True)
    
    # Pricing
    original_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    discounted_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Restrictions
    min_stay = models.IntegerField(default=1)  # days
    max_stay = models.IntegerField(default=365)  # days
    advance_booking = models.IntegerField(default=0)  # days
    
    def __str__(self):
        return self.title
    
    @property
    def discount_percentage(self):
        if self.original_price and self.discounted_price:
            return (1 - (self.discounted_price.amount / self.original_price.amount)) * 100
        return 0
    
    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        return self.valid_from <= now <= self.valid_until and self.is_active