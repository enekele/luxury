from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from djmoney.models.fields import MoneyField
from django.contrib.contenttypes.fields import GenericForeignKey



class User(AbstractUser):
    """Custom user model"""
    email = models.EmailField(_('email address'), unique=True)
    username = models.CharField(_('username'), max_length=150, unique=True, blank=True)
    first_name = models.CharField(_('first name'), max_length=150)
    last_name = models.CharField(_('last name'), max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    country = CountryField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True)
    preferred_currency = models.CharField(max_length=3, default='USD')
    preferred_language = models.CharField(max_length=5, default='en')
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    premium_expires = models.DateTimeField(null=True, blank=True)
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    total_bookings = models.IntegerField(default=0)
    total_spent = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', default=0)
    loyalty_points = models.IntegerField(default=0)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    promotional_emails = models.BooleanField(default=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'username']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def generate_referral_code(self):
        """Generate a unique referral code"""
        import string
        import random
        
        if not self.referral_code:
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not User.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.generate_referral_code()
        super().save(*args, **kwargs)
    
    @property
    def is_premium_active(self):
        """Check if premium subscription is active"""
        if not self.is_premium:
            return False
        if self.premium_expires is None:
            return True
        from django.utils import timezone
        return timezone.now() < self.premium_expires


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expires = models.DateField(null=True, blank=True)
    frequent_flyer_numbers = models.JSONField(default=dict, blank=True)
    travel_preferences = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"{self.user.email} Profile"


class UserActivity(models.Model):
    """User activity log"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.email} - {self.activity_type}"


class WishlistItem(models.Model):
    """User wishlist items"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
    
    def __str__(self):
        return f"{self.user.email} - {self.content_object}"