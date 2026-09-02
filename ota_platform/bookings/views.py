from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import datetime
from .models import Booking
from hotels.models import Hotel, HotelAvailability
from flights.models import Flight
from cars.models import CarRental
from tours.models import Tour, TourAvailability
from api.utils import validate_booking_dates, calculate_booking_total, generate_booking_reference


@login_required
def create_booking(request):
    """Create a new booking"""
    if request.method == 'POST':
        service_type = request.POST.get('service_type')
        service_id = request.POST.get('service_id')
        booking_date = request.POST.get('booking_date')
        check_in = request.POST.get('check_in')
        check_out = request.POST.get('check_out')
        guests = int(request.POST.get('guests', 1))
        contact_name = request.POST.get('contact_name')
        contact_email = request.POST.get('contact_email')
        contact_phone = request.POST.get('contact_phone', '')
        special_requests = request.POST.get('special_requests', '')
        
        # Get the service object
        service_object = None
        content_type = None
        
        if service_type == 'hotel':
            service_object = get_object_or_404(
                Hotel,
                id=service_id,
                is_active=True,
                is_available=True,
            )
            content_type = ContentType.objects.get_for_model(Hotel)
        elif service_type == 'flight':
            service_object = get_object_or_404(
                Flight,
                id=service_id,
                is_active=True,
                status='scheduled',
                available_seats__gt=0,
                departure_time__gt=timezone.now(),
            )
            content_type = ContentType.objects.get_for_model(Flight)
        elif service_type == 'car':
            service_object = get_object_or_404(
                CarRental,
                id=service_id,
                is_active=True,
                is_available=True,
            )
            content_type = ContentType.objects.get_for_model(CarRental)
        elif service_type == 'tour':
            service_object = get_object_or_404(
                Tour,
                id=service_id,
                is_active=True,
                is_available=True,
            )
            content_type = ContentType.objects.get_for_model(Tour)
        else:
            messages.error(request, 'Invalid service type.')
            return redirect('home')
        
        # Validate dates
        if check_in and check_out:
            date_errors = validate_booking_dates(check_in, check_out)
            if date_errors:
                for error in date_errors:
                    messages.error(request, error)
                return redirect(request.META.get('HTTP_REFERER', 'home'))
        
        # Calculate total amount
        booking_total = calculate_booking_total(
            service_object, 
            check_in or booking_date, 
            check_out or booking_date, 
            guests
        )
        
        if not booking_total:
            messages.error(request, 'Unable to calculate booking total.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))
        
        # Create booking
        booking = Booking.objects.create(
            user=request.user,
            content_type=content_type,
            object_id=service_object.id,
            booking_reference=generate_booking_reference(),
            booking_date=datetime.strptime(booking_date, '%Y-%m-%d').date() if booking_date else None,
            total_amount=booking_total['total'],
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            special_requests=special_requests,
            status='pending'
        )
        
        messages.success(request, f'Booking created successfully! Reference: {booking.booking_reference}')
        return redirect('user_bookings')
    
    return redirect('home')


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    if booking.status not in ['pending', 'confirmed']:
        return JsonResponse({
            'success': False,
            'message': 'This booking cannot be cancelled.'
        })
    
    booking.status = 'cancelled'
    booking.save()
    
    messages.success(request, 'Booking cancelled successfully.')
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'success': True,
            'message': 'Booking cancelled successfully.'
        })
    
    return redirect('user_bookings')


def check_availability(request):
    """Check availability for any service"""
    service_type = request.GET.get('service_type')
    service_id = request.GET.get('service_id')
    date = request.GET.get('date')
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    guests = int(request.GET.get('guests', 1))
    
    if not service_type or not service_id:
        return JsonResponse({
            'success': False,
            'message': 'Service type and ID are required.'
        })
    
    try:
        if service_type == 'hotel':
            hotel = get_object_or_404(Hotel, id=service_id, is_active=True)
            
            if not check_in or not check_out:
                return JsonResponse({
                    'success': False,
                    'message': 'Check-in and check-out dates are required for hotels.'
                })
            
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            # Check availability
            availability = HotelAvailability.objects.filter(
                hotel=hotel,
                date__range=[check_in_date, check_out_date],
                available_rooms__gte=guests
            )
            
            nights = (check_out_date - check_in_date).days
            available_nights = availability.count()
            
            if available_nights == nights:
                total_price = sum(av.price_per_night.amount for av in availability)
                return JsonResponse({
                    'success': True,
                    'available': True,
                    'total_price': total_price,
                    'nights': nights,
                    'price_per_night': total_price / nights if nights > 0 else 0,
                })
            else:
                return JsonResponse({
                    'success': True,
                    'available': False,
                    'message': 'Hotel is not available for the selected dates.'
                })
        
        elif service_type == 'tour':
            tour = get_object_or_404(Tour, id=service_id, is_active=True)
            
            if not date:
                return JsonResponse({
                    'success': False,
                    'message': 'Date is required for tours.'
                })
            
            tour_date = datetime.strptime(date, '%Y-%m-%d').date()
            availability = TourAvailability.objects.filter(
                tour=tour,
                date=tour_date,
                available_spots__gte=guests
            ).first()
            
            if availability:
                return JsonResponse({
                    'success': True,
                    'available': True,
                    'price_per_person': availability.price_per_person.amount,
                    'available_spots': availability.available_spots,
                    'total_price': availability.price_per_person.amount * guests
                })
            else:
                return JsonResponse({
                    'success': True,
                    'available': False,
                    'message': 'Tour is not available for the selected date.'
                })
        
        elif service_type == 'flight':
            flight = get_object_or_404(Flight, id=service_id, is_active=True)
            
            if flight.available_seats >= guests:
                return JsonResponse({
                    'success': True,
                    'available': True,
                    'price_per_person': flight.economy_price.amount,
                    'available_seats': flight.available_seats,
                    'total_price': flight.economy_price.amount * guests
                })
            else:
                return JsonResponse({
                    'success': True,
                    'available': False,
                    'message': 'Not enough seats available.'
                })
        
        elif service_type == 'car':
            car = get_object_or_404(CarRental, id=service_id, is_active=True)
            
            if car.is_available:
                days = 1
                if check_in and check_out:
                    check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
                    check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
                    days = (check_out_date - check_in_date).days
                
                return JsonResponse({
                    'success': True,
                    'available': True,
                    'price_per_day': car.price_per_day.amount,
                    'days': days,
                    'total_price': car.price_per_day.amount * days
                })
            else:
                return JsonResponse({
                    'success': True,
                    'available': False,
                    'message': 'Car is not available.'
                })
        
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid service type.'
            })
    
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid date format. Use YYYY-MM-DD.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while checking availability.'
        })


@login_required
@require_POST
def add_to_wishlist(request):
    """Add item to wishlist"""
    service_type = request.POST.get('service_type')
    service_id = request.POST.get('service_id')
    
    if not service_type or not service_id:
        return JsonResponse({
            'success': False,
            'message': 'Service type and ID are required.'
        })
    
    # Get content type
    content_type = None
    service_object = None
    
    if service_type == 'hotel':
        service_object = get_object_or_404(Hotel, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Hotel)
    elif service_type == 'flight':
        service_object = get_object_or_404(Flight, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Flight)
    elif service_type == 'car':
        service_object = get_object_or_404(CarRental, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(CarRental)
    elif service_type == 'tour':
        service_object = get_object_or_404(Tour, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Tour)
    else:
        return JsonResponse({
            'success': False,
            'message': 'Invalid service type.'
        })
    
    # Create or get wishlist item
    from users.models import WishlistItem
    
    wishlist_item, created = WishlistItem.objects.get_or_create(
        user=request.user,
        content_type=content_type,
        object_id=service_object.id
    )
    
    if created:
        message = f'{service_object.name} added to your wishlist!'
        success = True
    else:
        message = f'{service_object.name} is already in your wishlist.'
        success = True
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'success': success,
            'message': message,
            'in_wishlist': True
        })
    
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    """Remove item from wishlist"""
    from users.models import WishlistItem
    
    wishlist_item = get_object_or_404(WishlistItem, id=item_id, user=request.user)
    service_name = str(wishlist_item.content_object)
    wishlist_item.delete()
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'success': True,
            'message': f'{service_name} removed from wishlist.'
        })
    
    messages.success(request, f'{service_name} removed from wishlist.')
    return redirect('wishlist')
