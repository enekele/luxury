from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone
from .models import UserProfile, UserActivity, WishlistItem
from bookings.models import Booking
from payments.models import SubscriptionPackage, UserSubscription
from reviews.models import Review

User = get_user_model()


@login_required
def profile(request):
    """User profile view"""
    user = request.user
    
    # Get user statistics
    total_bookings = Booking.objects.filter(user=user).count()
    total_spent = Booking.objects.filter(user=user, status='confirmed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    recent_bookings = Booking.objects.filter(user=user).order_by('-created_at')[:5]
    recent_reviews = Review.objects.filter(user=user).order_by('-created_at')[:5]
    
    context = {
        'user': user,
        'total_bookings': total_bookings,
        'total_spent': total_spent,
        'recent_bookings': recent_bookings,
        'recent_reviews': recent_reviews,
    }
    
    return render(request, 'users/profile.html', context)


@login_required
def edit_profile(request):
    """Edit user profile"""
    user = request.user
    
    if request.method == 'POST':
        # Update user fields
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.phone = request.POST.get('phone', user.phone)
        user.country = request.POST.get('country', user.country)
        user.city = request.POST.get('city', user.city)
        user.address = request.POST.get('address', user.address)
        user.preferred_currency = request.POST.get('preferred_currency', user.preferred_currency)
        user.preferred_language = request.POST.get('preferred_language', user.preferred_language)
        
        # Update notification preferences
        user.email_notifications = request.POST.get('email_notifications') == 'on'
        user.sms_notifications = request.POST.get('sms_notifications') == 'on'
        user.promotional_emails = request.POST.get('promotional_emails') == 'on'
        
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        user.save()
        
        # Update profile fields
        profile = user.userprofile
        profile.bio = request.POST.get('bio', profile.bio)
        profile.website = request.POST.get('website', profile.website)
        profile.emergency_contact_name = request.POST.get('emergency_contact_name', profile.emergency_contact_name)
        profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', profile.emergency_contact_phone)
        profile.passport_number = request.POST.get('passport_number', profile.passport_number)
        
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'users/edit_profile.html', {'user': user})


@login_required
def bookings(request):
    """User bookings view"""
    user_bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by status if specified
    status = request.GET.get('status')
    if status:
        user_bookings = user_bookings.filter(status=status)
    
    context = {
        'bookings': user_bookings,
        'selected_status': status,
    }
    
    return render(request, 'users/bookings.html', context)


@login_required
def wishlist(request):
    """User wishlist view"""
    wishlist_items = WishlistItem.objects.filter(user=request.user).select_related('content_type')
    
    context = {
        'wishlist_items': wishlist_items,
    }
    
    return render(request, 'users/wishlist.html', context)


@login_required
def add_to_wishlist(request):
    """Add item to wishlist"""
    if request.method == 'POST':
        content_type_id = request.POST.get('content_type_id')
        object_id = request.POST.get('object_id')
        
        from django.contrib.contenttypes.models import ContentType
        content_type = get_object_or_404(ContentType, id=content_type_id)
        
        wishlist_item, created = WishlistItem.objects.get_or_create(
            user=request.user,
            content_type=content_type,
            object_id=object_id
        )
        
        if created:
            messages.success(request, 'Item added to wishlist!')
        else:
            messages.info(request, 'Item already in wishlist.')
    
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
def remove_from_wishlist(request, item_id):
    """Remove item from wishlist"""
    wishlist_item = get_object_or_404(WishlistItem, id=item_id, user=request.user)
    wishlist_item.delete()
    messages.success(request, 'Item removed from wishlist.')
    return redirect('wishlist')


@login_required
def loyalty_points(request):
    """User loyalty points view"""
    user = request.user
    
    # Calculate points from bookings
    confirmed_bookings = Booking.objects.filter(user=user, status='confirmed')
    
    context = {
        'user': user,
        'confirmed_bookings': confirmed_bookings,
    }
    
    return render(request, 'users/loyalty_points.html', context)


@login_required
def referrals(request):
    """User referrals view"""
    user = request.user
    referred_users = User.objects.filter(referred_by=user)
    
    context = {
        'user': user,
        'referred_users': referred_users,
        'referral_url': request.build_absolute_uri(f'/accounts/signup/?ref={user.referral_code}'),
    }
    
    return render(request, 'users/referrals.html', context)


@login_required
def subscription_packages(request):
    """Show available subscription packages and activate purchases."""
    packages = SubscriptionPackage.objects.filter(is_active=True).order_by('duration_days', 'price')
    current_subscription = UserSubscription.objects.filter(user=request.user, active=True).order_by('-expires_at').first()

    if request.method == 'POST':
        package_id = request.POST.get('package_id')
        package = get_object_or_404(SubscriptionPackage, pk=package_id, is_active=True)
        start_date = timezone.now()
        expires_at = start_date + timedelta(days=package.duration_days)

        # Expire previous active subscriptions
        UserSubscription.objects.filter(user=request.user, active=True).update(active=False)

        UserSubscription.objects.create(
            user=request.user,
            package=package,
            start_date=start_date,
            expires_at=expires_at,
            active=True,
        )

        request.user.is_premium = True
        request.user.premium_expires = expires_at
        request.user.save(update_fields=['is_premium', 'premium_expires'])

        messages.success(request, 'Subscription activated successfully!')
        return redirect('subscription_packages')

    context = {
        'packages': packages,
        'current_subscription': current_subscription,
    }
    return render(request, 'users/subscription_packages.html', context)


@login_required
def activity_log(request):
    """User activity log view"""
    activities = UserActivity.objects.filter(user=request.user)[:50]
    
    context = {
        'activities': activities,
    }
    
    return render(request, 'users/activity_log.html', context)


def public_profile(request, user_id):
    """Public user profile view"""
    user = get_object_or_404(User, id=user_id)
    
    # Only show public information
    public_reviews = Review.objects.filter(user=user, is_approved=True).order_by('-created_at')[:10]
    
    context = {
        'profile_user': user,
        'public_reviews': public_reviews,
    }
    
    return render(request, 'users/public_profile.html', context)