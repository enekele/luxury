from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel, City
from django.conf import settings

User = get_user_model()


class Hotel(BaseModel):
    """Hotel model"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='hotels')
    address = models.TextField()
    star_rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=3)
    price_per_night = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Amenities
    amenities = models.JSONField(default=list, blank=True)

    # Images
    main_image = models.ImageField(upload_to='hotels/', blank=True)
    
    # Status
    is_featured = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    
    # Contact info
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Booking settings
    check_in_time = models.TimeField(default='14:00')
    check_out_time = models.TimeField(default='11:00')
    cancellation_policy = models.TextField(blank=True)
    
    # Location
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Partner information
    partner_commission = models.DecimalField(max_digits=5, decimal_places=2, default=15.0)
    
    class Meta:
        ordering = ['-is_featured', 'name']
    
    def __str__(self):
        return self.name
    
    @property
    def average_rating(self):
        from reviews.models import Review
        reviews = Review.objects.filter(
            content_type__model='hotel',
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
            content_type__model='hotel',
            object_id=self.id,
            is_approved=True
        ).count()


class HotelImage(BaseModel):
    """Hotel images model"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='hotels/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_primary', 'id']
    
    def __str__(self):
        return f"{self.hotel.name} - Image {self.id}"


class RoomType(BaseModel):
    """Room types for hotels"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='room_types')
    name = models.CharField(max_length=100)
    description = models.TextField()
    max_occupancy = models.IntegerField(default=2)
    price_per_night = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Room details
    size_sqm = models.IntegerField(null=True, blank=True)
    bed_type = models.CharField(max_length=50, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    
    # Availability
    total_rooms = models.IntegerField(default=1)
    available_rooms = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['price_per_night']
    
    def __str__(self):
        return f"{self.hotel.name} - {self.name}"


class HotelAvailability(models.Model):
    """Hotel availability by date"""
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    available_rooms = models.IntegerField(default=0)
    price_per_night = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    class Meta:
        unique_together = ('hotel', 'date')
        ordering = ['date']
    
    def __str__(self):
        return f"{self.hotel.name} - {self.date}"


class HotelFacility(BaseModel):
    """Hotel facilities"""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)  # Bootstrap icon class
    category = models.CharField(max_length=50, choices=[
        ('general', 'General'),
        ('business', 'Business'),
        ('fitness', 'Fitness & Recreation'),
        ('internet', 'Internet'),
        ('parking', 'Parking'),
        ('services', 'Services'),
        ('accessibility', 'Accessibility'),
    ])
    
    def __str__(self):
        return self.name


class HotelPartner(BaseModel):
    """Hotel partner/supplier information"""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_partners')
    hotel = models.OneToOneField(Hotel, on_delete=models.CASCADE, related_name='partner')
    partner_name = models.CharField(max_length=200)
    partner_id = models.CharField(max_length=100, unique=True)
    api_endpoint = models.URLField(blank=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.0)
    
    # Link to local Partner account (optional)
    partner_profile = models.ForeignKey(
        'partners_dashboard.Partner',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hotel_partners',
    )

    # API credentials (encrypted)
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    
    # Contact information
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"{self.hotel.name} - {self.partner_name}"