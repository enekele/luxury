from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking


@receiver(post_save, sender=Booking)
def update_user_statistics(sender, instance, created, **kwargs):
    """Update user statistics when booking is created or updated"""
    if created:
        # Update user's total bookings count
        user = instance.user
        user.total_bookings += 1
        
        if instance.status == 'confirmed':
            user.total_spent += instance.total_amount
            # Award loyalty points (1 point per dollar spent)
            user.loyalty_points += int(instance.total_amount.amount)
        
        user.save()
    
    elif instance.status == 'confirmed' and not instance._state.adding:
        # If booking was just confirmed, update user stats
        user = instance.user
        user.total_spent += instance.total_amount
        user.loyalty_points += int(instance.total_amount.amount)
        user.save()