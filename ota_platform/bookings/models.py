from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from djmoney.models.fields import MoneyField
from core.models import BaseModel

User = get_user_model()


class Booking(BaseModel):
    """Universal booking model for all services"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    
    # Generic foreign key to any bookable service
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    room_type = models.ForeignKey(
        'hotels.RoomType',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bookings',
    )
    
    # Booking details
    booking_reference = models.CharField(max_length=20, unique=True, blank=True)
    booking_date = models.DateField(null=True, blank=True)
    
    # Pricing
    total_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ], default='pending')
    
    # concierg_request 
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    inventory_reserved = models.BooleanField(default=False)

    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("unpaid", "Unpaid"),
            ("pending", "Payment Pending"),
            ("paid", "Paid"),
            ("refunded", "Refunded"),
        ],
        default="unpaid",
    )

    expires_at = models.DateTimeField(null=True, blank=True)
    # Contact information
    contact_name = models.CharField(max_length=100)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Special requests
    special_requests = models.TextField(blank=True)
    
    def __str__(self):
        return f"Booking #{self.id} - {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.booking_reference:
            import random
            import string
            self.booking_reference = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Track affiliate referral if user was referred
        if self.status == 'confirmed' and not hasattr(self, '_affiliate_tracked'):
            from affiliates.models import AffiliateReferral
            try:
                referral = AffiliateReferral.objects.get(
                    referred_user=self.user,
                    converted=False
                )
                # This will be handled by the signal
                self._affiliate_tracked = True
            except AffiliateReferral.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
