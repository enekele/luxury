from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel, City

User = get_user_model()


class TourCategory(BaseModel):
    """Tour category model"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # Bootstrap icon class
    
    def __str__(self):
        return self.name


class TourOperator(BaseModel):
    """Tour operator/company model"""
    name = models.CharField(max_length=200)
    description = models.TextField()
    logo = models.ImageField(upload_to='tour_operators/', blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    
    # Verification
    is_verified = models.BooleanField(default=False)
    license_number = models.CharField(max_length=100, blank=True)
    
    # Location
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='tour_operators')
    address = models.TextField()
    
    def __str__(self):
        return self.name


class Tour(BaseModel):
    """Tour model"""
    operator = models.ForeignKey(TourOperator, on_delete=models.CASCADE, related_name='tours')
    category = models.ForeignKey(TourCategory, on_delete=models.CASCADE)
    
    # Basic info
    name = models.CharField(max_length=200)
    description = models.TextField()
    highlights = models.TextField(blank=True)
    
    # Location
    destination = models.ForeignKey(City, on_delete=models.CASCADE, related_name='tours')
    meeting_point = models.CharField(max_length=200)
    meeting_address = models.TextField()
    
    # Duration
    duration_days = models.IntegerField(default=1)
    duration_hours = models.IntegerField(default=8)
    
    # Pricing
    price_per_person = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    child_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    # Capacity
    max_participants = models.IntegerField(default=15)
    min_participants = models.IntegerField(default=1)
    
    # Schedule
    schedule = models.JSONField(default=list, blank=True)  # Daily itinerary
    
    # What's included/excluded
    included = models.JSONField(default=list, blank=True)
    excluded = models.JSONField(default=list, blank=True)
    
    # Requirements
    difficulty_level = models.CharField(max_length=20, choices=[
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('challenging', 'Challenging'),
        ('difficult', 'Difficult'),
    ], default='easy')
    
    age_restriction = models.CharField(max_length=50, blank=True)
    fitness_level = models.CharField(max_length=50, blank=True)
    
    # Languages
    languages = models.JSONField(default=list, blank=True)
    
    # Cancellation policy
    cancellation_policy = models.TextField(blank=True)
    
    # Images
    main_image = models.ImageField(upload_to='tours/', blank=True)
    
    # Availability
    available_days = models.JSONField(default=list, blank=True)  # Days of week
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Optional link to a Partner account
    partner_profile = models.ForeignKey(
        'partners_dashboard.Partner',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tours',
    )
    
    # Status
    is_featured = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    
    # Tags
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-is_featured', 'name']
    
    def __str__(self):
        return self.name
    
    @property
    def average_rating(self):
        from reviews.models import Review
        reviews = Review.objects.filter(
            content_type__model='tour',
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
            content_type__model='tour',
            object_id=self.id,
            is_approved=True
        ).count()
    
    @property
    def duration_display(self):
        if self.duration_days > 1:
            return f"{self.duration_days} days"
        else:
            return f"{self.duration_hours} hours"


class TourImage(BaseModel):
    """Tour images"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='tours/')
    caption = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_primary', 'id']
    
    def __str__(self):
        return f"{self.tour.name} - Image {self.id}"


class TourAvailability(models.Model):
    """Tour availability by date"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='availability')
    date = models.DateField()
    available_spots = models.IntegerField(default=0)
    price_per_person = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    class Meta:
        unique_together = ('tour', 'date')
        ordering = ['date']
    
    def __str__(self):
        return f"{self.tour.name} - {self.date}"


class TourGuide(BaseModel):
    """Tour guide model"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField()
    languages = models.JSONField(default=list, blank=True)
    specialties = models.JSONField(default=list, blank=True)
    experience_years = models.IntegerField(default=0)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    license_number = models.CharField(max_length=100, blank=True)
    
    # Profile
    profile_picture = models.ImageField(upload_to='tour_guides/', blank=True)
    
    def __str__(self):
        return self.user.get_full_name()
    
    @property
    def average_rating(self):
        from reviews.models import Review
        reviews = Review.objects.filter(
            content_type__model='tourguide',
            object_id=self.id,
            is_approved=True
        )
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return 0


class TourBooking(BaseModel):
    """Tour booking model"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    guide = models.ForeignKey(TourGuide, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Booking details
    booking_date = models.DateField()
    participants = models.IntegerField(default=1)
    children = models.IntegerField(default=0)
    
    # Pricing
    total_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ], default='pending')
    
    # Contact info
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    
    # Special requests
    special_requests = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.tour.name} - {self.user.get_full_name()}"


class TourReview(BaseModel):
    """Tour review model (extends base Review)"""
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='tour_reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking = models.ForeignKey(TourBooking, on_delete=models.CASCADE, null=True, blank=True)
    
    # Ratings
    overall_rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    value_rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    guide_rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    organization_rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    
    # Review content
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Verification
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.tour.name} - {self.user.get_full_name()}"