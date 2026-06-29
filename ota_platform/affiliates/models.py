from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from core.models import BaseModel
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

User = get_user_model()


class AffiliateProfile(BaseModel):
    """Affiliate marketer profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate_profile')
    affiliate_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    # Business Information
    company_name = models.CharField(max_length=200, blank=True)
    business_type = models.CharField(max_length=50, choices=[
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('agency', 'Travel Agency'),
        ('blogger', 'Travel Blogger'),
        ('influencer', 'Social Media Influencer'),
    ], default='individual')
    
    # Contact Information
    business_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Social Media
    social_media_links = models.JSONField(default=dict, blank=True)
    follower_count = models.IntegerField(default=0)
    
    # Commission Settings
    commission_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=5.0,
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    
    # KYC Information
    kyc_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ], default='pending')
    
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_approved_at = models.DateTimeField(null=True, blank=True)
    kyc_rejection_reason = models.TextField(blank=True)
    
    # Documents
    id_document = models.FileField(upload_to='kyc/id_documents/', blank=True)
    business_license = models.FileField(upload_to='kyc/business_licenses/', blank=True)
    tax_document = models.FileField(upload_to='kyc/tax_documents/', blank=True)
    
    # Bank Information
    bank_name = models.CharField(max_length=200, blank=True)
    account_holder_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    routing_number = models.CharField(max_length=20, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    
    # Statistics
    total_referrals = models.IntegerField(default=0)
    total_bookings = models.IntegerField(default=0)
    total_earnings = MoneyField(max_digits=12, decimal_places=2, default_currency='USD', default=0)
    pending_earnings = MoneyField(max_digits=12, decimal_places=2, default_currency='USD', default=0)
    paid_earnings = MoneyField(max_digits=12, decimal_places=2, default_currency='USD', default=0)
    
    # Status
    is_approved = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True)
    
    # Agreement
    agreement_accepted = models.BooleanField(default=False)
    agreement_accepted_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.affiliate_id}"
    
    @property
    def conversion_rate(self):
        if self.total_referrals > 0:
            return (self.total_bookings / self.total_referrals) * 100
        return 0
    
    @property
    def average_commission_per_booking(self):
        if self.total_bookings > 0:
            return self.total_earnings.amount / self.total_bookings
        return 0

class AffiliateReferral(models.Model):
    """Track referrals made by affiliates"""
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='referrals')
    referred_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_received')
    referred_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField()
    converted = models.BooleanField(default=False)
    conversion_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Referral by {self.affiliate.user.get_full_name()} to {self.referred_user.get_full_name()}"
    

class AffiliatePromoCode(BaseModel):
    """Affiliate-specific promo codes"""
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='promo_codes')
    code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=200)
    
    # Discount Settings
    discount_type = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_discount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    # Usage Limits
    usage_limit = models.IntegerField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True) 
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Service Restrictions
    service_type = models.CharField(max_length=20, choices=[
        ('all', 'All Services'),
        ('hotel', 'Hotels'),
        ('flight', 'Flights'),
        ('car', 'Car Rentals'),
        ('tour', 'Tours'),
    ], default='all')
    
    # Minimum Requirements
    min_amount = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    def __str__(self):
        return f"{self.code} - {self.affiliate.user.get_full_name()}"
    
    @property
    def is_valid(self):
        """Return True if promo code is active, within its validity window and under usage limits."""
        from django.utils import timezone

        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.usage_limit is not None and self.usage_limit > 0 and self.usage_count >= self.usage_limit:
            return False
        return True


class AffiliateCommission(BaseModel):
    """Monetary commission record associated with a referral/booking."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ]

    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='commissions')
    amount = MoneyField(max_digits=12, decimal_places=2, default_currency='USD', default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    approved_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def mark_paid(self):
        from django.utils import timezone
        self.status = 'paid'
        self.processed_at = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        self.save(update_fields=['status', 'processed_at'])

    def __str__(self):
        return f"Commission {self.id} - {self.affiliate.user.get_full_name()} - {self.amount}"


class AffiliatePayment(BaseModel):
    """Affiliate payment records"""
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='payments')
    amount = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    payment_method = models.CharField(max_length=50, choices=[
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('check', 'Check'),
    ])
    
    # Payment Details
    payment_reference = models.CharField(max_length=100, unique=True)
    payment_date = models.DateTimeField()
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    
    # Included Commissions
    commissions = models.ManyToManyField(AffiliateCommission, related_name='payments')
    
    # Notes
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Payment to {self.affiliate.user.get_full_name()} - ${self.amount.amount}"


class AffiliateClick(models.Model):
    """Track affiliate link clicks"""
    affiliate = models.ForeignKey(AffiliateProfile, on_delete=models.CASCADE, related_name='clicks')
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    referrer = models.URLField(blank=True)
    landing_page = models.URLField()
    
    # Conversion tracking
    converted = models.BooleanField(default=False)
    conversion_value = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    
    class Meta:
        ordering = ['-clicked_at']
    
    def __str__(self):
        return f"Click from {self.affiliate.user.get_full_name()} at {self.clicked_at}"


class AffiliateResource(BaseModel):
    """Marketing resources for affiliates"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    resource_type = models.CharField(max_length=50, choices=[
        ('banner', 'Banner'),
        ('text_link', 'Text Link'),
        ('email_template', 'Email Template'),
        ('social_post', 'Social Media Post'),
        ('landing_page', 'Landing Page'),
        ('guide', 'Marketing Guide'),
    ])
    
    # Content
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to='affiliate_resources/', blank=True)
    download_file = models.FileField(upload_to='affiliate_resources/', blank=True)
    
    # Targeting
    service_type = models.CharField(max_length=20, choices=[
        ('all', 'All Services'),
        ('hotel', 'Hotels'),
        ('flight', 'Flights'),
        ('car', 'Car Rentals'),
        ('tour', 'Tours'),
    ], default='all')
    
    # Statistics
    download_count = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title