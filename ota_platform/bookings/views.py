from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import datetime
from .models import Booking
from hotels.inventory import (
    RoomInventoryError,
    quote_room_stay,
    release_booking_room_inventory,
    reserve_room_inventory,
)
from hotels.models import Hotel, RoomType
from flights.models import Flight
from cars.models import CarRental
from tours.models import Tour, TourAvailability
from api.utils import validate_booking_dates, calculate_booking_total, generate_booking_reference


def _booking_error(request, message, *, status=400):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {'success': False, 'message': message},
            status=status,
        )
    messages.error(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def _positive_integer(value, label, default=1):
    try:
        parsed = int(value if value not in (None, '') else default)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a whole number.')
    if parsed < 1:
        raise ValueError(f'{label} must be at least 1.')
    return parsed


@login_required
@require_POST
def create_booking(request):
    """Create a new booking"""
    service_type = request.POST.get('service_type', '').strip()
    service_id = request.POST.get('service_id')
    booking_date = request.POST.get('booking_date')
    check_in = request.POST.get('check_in')
    check_out = request.POST.get('check_out')
    contact_name = request.POST.get('contact_name', '').strip()
    contact_email = request.POST.get('contact_email', '').strip()
    contact_phone = request.POST.get('contact_phone', '').strip()
    special_requests = request.POST.get('special_requests', '').strip()

    try:
        guests = _positive_integer(request.POST.get('guests'), 'Guests')
        quantity = _positive_integer(
            request.POST.get('rooms') or request.POST.get('quantity'),
            'Rooms',
        )
    except ValueError as error:
        return _booking_error(request, str(error))

    if not contact_name or not contact_email:
        return _booking_error(request, 'Contact name and email are required.')
    try:
        validate_email(contact_email)
    except ValidationError:
        return _booking_error(request, 'Enter a valid contact email address.')

    if service_type == 'hotel':
        hotel = get_object_or_404(
            Hotel,
            id=service_id,
            is_active=True,
            is_available=True,
        )
        room_type_id = request.POST.get('room_type')
        if not room_type_id:
            return _booking_error(request, 'Select a room category to continue.')
        if not check_in or not check_out:
            return _booking_error(
                request,
                'Check-in and check-out dates are required.',
            )

        date_errors = validate_booking_dates(check_in, check_out)
        if date_errors:
            return _booking_error(request, date_errors[0])
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()

        with transaction.atomic():
            room_type = get_object_or_404(
                RoomType.objects.select_for_update().select_related('hotel'),
                id=room_type_id,
                hotel=hotel,
                is_active=True,
            )
            try:
                quote = quote_room_stay(
                    room_type,
                    check_in_date,
                    check_out_date,
                    rooms=quantity,
                    guests=guests,
                    lock_inventory=True,
                )
            except RoomInventoryError as error:
                return _booking_error(request, str(error))

            booking = Booking.objects.create(
                user=request.user,
                content_type=ContentType.objects.get_for_model(Hotel),
                object_id=hotel.id,
                room_type=room_type,
                booking_reference=generate_booking_reference(),
                booking_date=check_in_date,
                check_in=check_in_date,
                check_out=check_out_date,
                quantity=quantity,
                inventory_reserved=True,
                total_amount=quote['total'],
                contact_name=contact_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                special_requests=special_requests,
                status='pending',
            )
            reserve_room_inventory(quote)

        messages.success(
            request,
            f'Booking created successfully! Reference: {booking.booking_reference}',
        )
        return redirect('user_bookings')

    service_object = None
    content_type = None
    if service_type == 'flight':
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
        return _booking_error(request, 'Invalid service type.')

    calculation_start = check_in or booking_date
    calculation_end = check_out or booking_date
    if not calculation_start or not calculation_end:
        return _booking_error(request, 'Choose a booking date to continue.')
    if check_in and check_out:
        date_errors = validate_booking_dates(check_in, check_out)
        if date_errors:
            return _booking_error(request, date_errors[0])

    booking_total = calculate_booking_total(
        service_object,
        calculation_start,
        calculation_end,
        guests,
    )
    if not booking_total:
        return _booking_error(request, 'Unable to calculate booking total.')

    try:
        parsed_booking_date = (
            datetime.strptime(booking_date, '%Y-%m-%d').date()
            if booking_date
            else None
        )
        parsed_check_in = (
            datetime.strptime(check_in, '%Y-%m-%d').date() if check_in else None
        )
        parsed_check_out = (
            datetime.strptime(check_out, '%Y-%m-%d').date() if check_out else None
        )
    except ValueError:
        return _booking_error(request, 'Invalid date format. Use YYYY-MM-DD.')

    booking = Booking.objects.create(
        user=request.user,
        content_type=content_type,
        object_id=service_object.id,
        booking_reference=generate_booking_reference(),
        booking_date=parsed_booking_date,
        check_in=parsed_check_in,
        check_out=parsed_check_out,
        quantity=quantity,
        total_amount=booking_total['total'],
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        special_requests=special_requests,
        status='pending',
    )

    messages.success(
        request,
        f'Booking created successfully! Reference: {booking.booking_reference}',
    )
    return redirect('user_bookings')


@login_required
@require_POST
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            id=booking_id,
            user=request.user,
        )

        if booking.status not in ['pending', 'confirmed']:
            return JsonResponse({
                'success': False,
                'message': 'This booking cannot be cancelled.'
            })

        release_booking_room_inventory(booking)
        booking.status = 'cancelled'
        booking.save(update_fields=['status', 'updated_at'])
    
    messages.success(request, 'Booking cancelled successfully.')
    
    if (
        request.headers.get('Content-Type') == 'application/json'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ):
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
    try:
        guests = _positive_integer(request.GET.get('guests'), 'Guests')
        rooms = _positive_integer(request.GET.get('rooms'), 'Rooms')
    except ValueError as error:
        return JsonResponse({
            'success': False,
            'message': str(error),
        })
    
    if not service_type or not service_id:
        return JsonResponse({
            'success': False,
            'message': 'Service type and ID are required.'
        })
    
    try:
        if service_type == 'hotel':
            hotel = get_object_or_404(
                Hotel,
                id=service_id,
                is_active=True,
                is_available=True,
            )
            
            if not check_in or not check_out:
                return JsonResponse({
                    'success': False,
                    'message': 'Check-in and check-out dates are required for hotels.'
                })
            
            date_errors = validate_booking_dates(check_in, check_out)
            if date_errors:
                return JsonResponse({
                    'success': False,
                    'message': date_errors[0],
                })
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            room_type_id = request.GET.get('room_type')
            if not room_type_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Select a room category.',
                })

            room_type = get_object_or_404(
                RoomType.objects.select_related('hotel'),
                id=room_type_id,
                hotel=hotel,
                is_active=True,
            )
            try:
                quote = quote_room_stay(
                    room_type,
                    check_in_date,
                    check_out_date,
                    rooms=rooms,
                    guests=guests,
                )
            except RoomInventoryError as error:
                return JsonResponse({
                    'success': True,
                    'available': False,
                    'message': str(error),
                })

            return JsonResponse({
                'success': True,
                'available': True,
                'room_type': {
                    'id': room_type.id,
                    'name': room_type.name,
                },
                'total_price': f'{quote["total"].amount:.2f}',
                'currency': str(quote['total'].currency),
                'nights': quote['nights'],
                'rooms': rooms,
                'price_per_night': (
                    f'{quote["average_nightly_rate"].amount:.2f}'
                ),
                'available_rooms': min(
                    night['available_rooms']
                    for night in quote['nightly_inventory']
                ),
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
    
    if (
        request.headers.get('Content-Type') == 'application/json'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    ):
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
