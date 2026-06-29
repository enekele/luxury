from django.db.models.signals import post_save
from django.dispatch import receiver
from bookings.models import Booking
from .models import AffiliateProfile, AffiliateReferral, AffiliateCommission


@receiver(post_save, sender=Booking)
def create_affiliate_commission(sender, instance, created, **kwargs):
    """Create affiliate commission when booking is confirmed"""
    if created and instance.status == 'confirmed':
        # Check if this user was referred by an affiliate
        try:
            referral = AffiliateReferral.objects.get(
                referred_user=instance.user,
                converted=False
            )
            
            # Mark referral as converted
            referral.converted = True
            referral.conversion_date = instance.created_at
            referral.first_booking_amount = instance.total_amount
            referral.save()
            
            # Calculate commission
            affiliate = referral.affiliate
            commission_amount = instance.total_amount.amount * (affiliate.commission_rate / 100)
            
            # Create commission record
            AffiliateCommission.objects.create(
                affiliate=affiliate,
                booking=instance,
                referral=referral,
                commission_rate=affiliate.commission_rate,
                booking_amount=instance.total_amount,
                commission_amount=commission_amount,
                status='pending'
            )
            
            # Update affiliate statistics
            affiliate.total_bookings += 1
            affiliate.pending_earnings += commission_amount
            affiliate.save()
            
        except AffiliateReferral.DoesNotExist:
            pass