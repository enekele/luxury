from django.core.cache import cache
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
import hashlib
import json


def cache_key_generator(prefix, **kwargs):
    """
    Generate cache key from parameters
    """
    key_data = json.dumps(kwargs, sort_keys=True, default=str)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()
    return f"{prefix}:{key_hash}"


def get_cached_data(cache_key, timeout=300):
    """
    Get data from cache
    """
    return cache.get(cache_key)


def set_cached_data(cache_key, data, timeout=300):
    """
    Set data in cache
    """
    cache.set(cache_key, data, timeout)


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    
    return c * r


def convert_currency(amount, from_currency, to_currency):
    """
    Convert currency using exchange rates
    """
    from core.models import Currency
    
    if from_currency == to_currency:
        return amount
    
    try:
        from_curr = Currency.objects.get(code=from_currency, is_active=True)
        to_curr = Currency.objects.get(code=to_currency, is_active=True)
        
        # Convert to USD first, then to target currency
        usd_amount = amount / from_curr.exchange_rate
        converted_amount = usd_amount * to_curr.exchange_rate
        
        return round(converted_amount, 2)
    except Currency.DoesNotExist:
        return amount


def validate_booking_dates(check_in, check_out):
    """
    Validate booking dates
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    errors = []
    
    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        
        today = timezone.now().date()
        
        if check_in_date < today:
            errors.append("Check-in date cannot be in the past")
        
        if check_out_date <= check_in_date:
            errors.append("Check-out date must be after check-in date")
        
        if (check_in_date - today).days > 365:
            errors.append("Booking cannot be made more than 365 days in advance")
        
        if (check_in_date - today).days < 0:
            errors.append("Check-in must be at least today")
            
    except ValueError:
        errors.append("Invalid date format. Use YYYY-MM-DD")
    
    return errors


def calculate_booking_total(service_object, check_in, check_out, guests=1, extras=None):
    """
    Calculate total booking amount
    """
    from datetime import datetime
    
    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        nights = (check_out_date - check_in_date).days
        
        if hasattr(service_object, 'price_per_night'):
            base_price = service_object.price_per_night.amount * nights
        elif hasattr(service_object, 'price_per_day'):
            base_price = service_object.price_per_day.amount * nights
        elif hasattr(service_object, 'price_per_person'):
            base_price = service_object.price_per_person.amount * guests
        else:
            base_price = 0
        
        # Add extras if provided
        extras_total = 0
        if extras:
            for extra in extras:
                extras_total += extra.get('price', 0) * extra.get('quantity', 1)
        
        total = base_price + extras_total
        
        return {
            'base_price': base_price,
            'extras_total': extras_total,
            'total': total,
            'nights': nights if hasattr(service_object, 'price_per_night') else None,
            'guests': guests
        }
        
    except ValueError:
        return None


def send_booking_confirmation_email(booking):
    """
    Send booking confirmation email
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    subject = f"Booking Confirmation - {booking.booking_reference}"
    
    html_message = render_to_string('emails/booking_confirmation.html', {
        'booking': booking,
        'user': booking.user,
        'service': booking.content_object
    })
    
    try:
        send_mail(
            subject=subject,
            message='',  # Plain text version
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        # Log the error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send booking confirmation email: {e}")
        return False


def generate_booking_reference():
    """
    Generate unique booking reference
    """
    import random
    import string
    from bookings.models import Booking
    
    while True:
        reference = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Booking.objects.filter(booking_reference=reference).exists():
            return reference


def service_is_bookable(service_object):
    """Return whether a supported travel service is open for new bookings."""
    from django.utils import timezone

    if service_object is None or not getattr(service_object, 'is_active', False):
        return False

    model_name = service_object._meta.model_name
    if model_name == 'flight':
        return (
            service_object.status == 'scheduled'
            and service_object.available_seats > 0
            and service_object.departure_time > timezone.now()
        )

    if model_name in {'hotel', 'carrental', 'tour'}:
        return bool(service_object.is_available)

    return False


def check_service_availability(service_object, date, guests=1):
    """
    Check if service is available for given date and guests
    """
    if not service_is_bookable(service_object):
        return False

    if hasattr(service_object, 'availability'):
        availability = service_object.availability.filter(date=date).first()
        if availability:
            if hasattr(availability, 'available_rooms'):
                return availability.available_rooms >= guests
            elif hasattr(availability, 'available_spots'):
                return availability.available_spots >= guests
    
    return service_object.is_available if hasattr(service_object, 'is_available') else True


def apply_promotion(total_amount, promotion_code, service_type='all'):
    """
    Apply promotion discount to total amount
    """
    from core.models import Promotion
    from django.utils import timezone
    
    try:
        promotion = Promotion.objects.get(
            code=promotion_code,
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_until__gte=timezone.now()
        )
        
        if promotion.service_type != 'all' and promotion.service_type != service_type:
            return {
                'success': False,
                'message': 'Promotion not valid for this service type'
            }
        
        if promotion.usage_limit and promotion.used_count >= promotion.usage_limit:
            return {
                'success': False,
                'message': 'Promotion usage limit reached'
            }
        
        if promotion.min_amount and total_amount < promotion.min_amount.amount:
            return {
                'success': False,
                'message': f'Minimum amount ${promotion.min_amount.amount} required'
            }
        
        # Calculate discount
        if promotion.discount_type == 'percentage':
            discount = total_amount * (promotion.discount_value / 100)
        else:
            discount = promotion.discount_value
        
        # Apply maximum discount limit
        if promotion.max_discount and discount > promotion.max_discount.amount:
            discount = promotion.max_discount.amount
        
        final_amount = max(0, total_amount - discount)
        
        return {
            'success': True,
            'discount': discount,
            'final_amount': final_amount,
            'promotion': promotion
        }
        
    except Promotion.DoesNotExist:
        return {
            'success': False,
            'message': 'Invalid promotion code'
        }
