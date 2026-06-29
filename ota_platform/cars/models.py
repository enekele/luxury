from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel, City

User = get_user_model()


class CarBrand(BaseModel):
    """Car brand model"""
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='car_brands/', blank=True)
    
    def __str__(self):
        return self.name


class CarModel(BaseModel):
    """Car model"""
    brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    year = models.IntegerField()
    
    def __str__(self):
        return f"{self.brand.name} {self.name} ({self.year})"


class CarRentalCompany(BaseModel):
    """Car rental company model"""
    name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='car_companies/', blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    def __str__(self):
        return self.name


class CarRental(BaseModel):
    """Car rental model"""
    company = models.ForeignKey(CarRentalCompany, on_delete=models.CASCADE)
    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE)
    
    # Location
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='car_rentals')
    pickup_location = models.CharField(max_length=200)
    pickup_address = models.TextField()
    
    # Car details
    year = models.IntegerField()
    color = models.CharField(max_length=50, blank=True)
    license_plate = models.CharField(max_length=20, blank=True)
    
    # Specifications
    category = models.CharField(max_length=50, choices=[
        ('economy', 'Economy'),
        ('compact', 'Compact'),
        ('intermediate', 'Intermediate'),
        ('standard', 'Standard'),
        ('full_size', 'Full Size'),
        ('premium', 'Premium'),
        ('luxury', 'Luxury'),
        ('suv', 'SUV'),
        ('minivan', 'Minivan'),
        ('convertible', 'Convertible'),
    ])
    
    # Capacity
    passengers = models.IntegerField(default=4)
    bags = models.IntegerField(default=2)
    doors = models.IntegerField(default=4)
    
    # Features
    transmission = models.CharField(max_length=20, choices=[
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
    ], default='automatic')
    
    fuel_type = models.CharField(max_length=20, choices=[
        ('gasoline', 'Gasoline'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
    ], default='gasoline')
    
    air_conditioning = models.BooleanField(default=True)
    gps = models.BooleanField(default=False)
    
    # Pricing
    price_per_day = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    price_per_week = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    price_per_month = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    # Availability
    is_available = models.BooleanField(default=True)
    # Optional link to a Partner account
    partner_profile = models.ForeignKey(
        'partners_dashboard.Partner',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='car_rentals',
    )
    
    # Insurance and policies
    insurance_included = models.BooleanField(default=False)
    insurance_cost = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    # Requirements
    minimum_age = models.IntegerField(default=21)
    driving_license_required = models.BooleanField(default=True)
    credit_card_required = models.BooleanField(default=True)
    
    # Additional costs
    security_deposit = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Images
    main_image = models.ImageField(upload_to='car_rentals/', blank=True)
    
    # Mileage
    mileage_limit = models.IntegerField(null=True, blank=True)  # km per day
    extra_mileage_cost = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    class Meta:
        ordering = ['price_per_day']
    
    def __str__(self):
        return f"{self.car_model} - {self.city.name}"
    
    @property
    def average_rating(self):
        from reviews.models import Review
        reviews = Review.objects.filter(
            content_type__model='carrental',
            object_id=self.id,
            is_approved=True
        )
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return 0
    
    @property
    def total_reviews(self):
        from reviews.models import Review
        return Review.objects.filter(
            content_type__model='carrental',
            object_id=self.id,
            is_approved=True
        ).count()


class CarRentalImage(BaseModel):
    """Car rental images"""
    car_rental = models.ForeignKey(CarRental, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='car_rentals/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_primary', 'id']
    
    def __str__(self):
        return f"{self.car_rental} - Image {self.id}"


class CarRentalAvailability(models.Model):
    """Car rental availability by date"""
    car_rental = models.ForeignKey(CarRental, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    price_per_day = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    class Meta:
        unique_together = ('car_rental', 'date')
        ordering = ['date']
    
    def __str__(self):
        return f"{self.car_rental} - {self.date}"


class CarRentalLocation(BaseModel):
    """Car rental pickup/dropoff locations"""
    company = models.ForeignKey(CarRentalCompany, on_delete=models.CASCADE, related_name='locations')
    name = models.CharField(max_length=200)
    address = models.TextField()
    city = models.ForeignKey(City, on_delete=models.CASCADE)
    
    # Contact
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Operating hours
    opening_hours = models.JSONField(default=dict, blank=True)
    
    # Location type
    location_type = models.CharField(max_length=50, choices=[
        ('airport', 'Airport'),
        ('city_center', 'City Center'),
        ('hotel', 'Hotel'),
        ('train_station', 'Train Station'),
        ('other', 'Other'),
    ], default='city_center')
    
    # Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    def __str__(self):
        return f"{self.company.name} - {self.name}"


class CarRentalExtra(BaseModel):
    """Additional services and extras"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    price_type = models.CharField(max_length=20, choices=[
        ('per_day', 'Per Day'),
        ('per_rental', 'Per Rental'),
        ('per_week', 'Per Week'),
    ], default='per_day')
    
    category = models.CharField(max_length=50, choices=[
        ('navigation', 'Navigation'),
        ('child_safety', 'Child Safety'),
        ('comfort', 'Comfort'),
        ('protection', 'Protection'),
        ('mobility', 'Mobility'),
    ])
    
    def __str__(self):
        return self.name