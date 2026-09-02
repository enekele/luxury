from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Hotel, RoomType, HotelAvailability
from core.models import City, Country
from reviews.models import Review


def hotel_list(request):
    """Hotel listing view"""
    hotels = Hotel.objects.filter(is_active=True, is_available=True)
    
    # Filters
    city_id = request.GET.get('city')
    star_rating = request.GET.get('star_rating')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    amenities = request.GET.getlist('amenities')
    
    if city_id:
        hotels = hotels.filter(city_id=city_id)
    
    if star_rating:
        hotels = hotels.filter(star_rating=star_rating)
    
    if min_price:
        hotels = hotels.filter(price_per_night__gte=min_price)
    
    if max_price:
        hotels = hotels.filter(price_per_night__lte=max_price)
    
    if amenities:
        for amenity in amenities:
            hotels = hotels.filter(amenities__contains=amenity)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        hotels = hotels.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(city__name__icontains=search_query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort', 'name')
    if sort_by == 'price_low':
        hotels = hotels.order_by('price_per_night')
    elif sort_by == 'price_high':
        hotels = hotels.order_by('-price_per_night')
    elif sort_by == 'rating':
        hotels = hotels.annotate(
            avg_rating=Avg('reviews__rating')
        ).order_by('-avg_rating')
    else:
        hotels = hotels.order_by('-is_featured', 'name')
    
    # Pagination
    paginator = Paginator(hotels, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get cities for filter
    cities = City.objects.filter(is_active=True, hotels__isnull=False).distinct()
    
    context = {
        'hotels': page_obj,
        'cities': cities,
        'selected_city': city_id,
        'selected_star_rating': star_rating,
        'min_price': min_price,
        'max_price': max_price,
        'selected_amenities': amenities,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    
    return render(request, 'hotels/hotel_list.html', context)


def hotel_detail(request, hotel_id):
    """Hotel detail view"""
    hotel = get_object_or_404(
        Hotel,
        id=hotel_id,
        is_active=True,
        is_available=True,
    )
    
    # Get room types
    room_types = hotel.room_types.filter(is_active=True)
    
    # Get reviews
    reviews = Review.objects.filter(
        content_type__model='hotel',
        object_id=hotel.id,
        is_approved=True
    ).order_by('-created_at')
    
    # Get availability for next 30 days
    today = timezone.now().date()
    end_date = today + timedelta(days=30)
    availability = HotelAvailability.objects.filter(
        room_type__hotel=hotel,
        room_type__is_active=True,
        date__range=[today, end_date]
    ).select_related('room_type').order_by('date', 'room_type__name')
    
    # Get nearby hotels
    nearby_hotels = Hotel.objects.filter(
        city=hotel.city,
        is_active=True,
        is_available=True
    ).exclude(id=hotel.id)[:4]
    
    # Check if user can review
    can_review = False
    if request.user.is_authenticated:
        from bookings.models import Booking
        user_bookings = Booking.objects.filter(
            user=request.user,
            content_type__model='hotel',
            object_id=hotel.id,
            status='confirmed'
        )
        can_review = user_bookings.exists()
    
    context = {
        'hotel': hotel,
        'room_types': room_types,
        'reviews': reviews,
        'availability': availability,
        'nearby_hotels': nearby_hotels,
        'can_review': can_review,
    }
    
    return render(request, 'hotels/hotel_detail.html', context)


def hotel_search(request):
    """Hotel search view"""
    if request.method == 'GET':
        destination = request.GET.get('destination')
        check_in = request.GET.get('check_in')
        check_out = request.GET.get('check_out')
        guests = request.GET.get('guests', 1)
        
        hotels = Hotel.objects.filter(is_active=True, is_available=True)
        
        if destination:
            hotels = hotels.filter(
                Q(city__name__icontains=destination) |
                Q(city__country__name__icontains=destination)
            )
        
        if check_in and check_out:
            try:
                check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
                check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
                
                # Filter by availability
                available_hotels = []
                for hotel in hotels:
                    days_needed = (check_out_date - check_in_date).days
                    room_type_available = hotel.room_types.filter(
                        is_active=True,
                        availability__date__gte=check_in_date,
                        availability__date__lt=check_out_date,
                        availability__available_rooms__gt=0,
                    ).distinct()
                    if any(
                        room_type.availability.filter(
                            date__gte=check_in_date,
                            date__lt=check_out_date,
                            available_rooms__gt=0,
                        ).count() == days_needed
                        for room_type in room_type_available
                    ):
                        available_hotels.append(hotel.id)
                
                hotels = hotels.filter(id__in=available_hotels)
            except ValueError:
                pass
        
        # Pagination
        paginator = Paginator(hotels, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'hotels': page_obj,
            'destination': destination,
            'check_in': check_in,
            'check_out': check_out,
            'guests': guests,
        }
        
        return render(request, 'hotels/hotel_search.html', context)
    
    return render(request, 'hotels/hotel_search.html')


def check_availability(request, hotel_id):
    """AJAX endpoint to check hotel availability"""
    hotel = get_object_or_404(
        Hotel,
        id=hotel_id,
        is_active=True,
        is_available=True,
    )
    
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    
    if not check_in or not check_out:
        return JsonResponse({'error': 'Check-in and check-out dates are required'})
    
    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        
        if check_in_date >= check_out_date:
            return JsonResponse({'error': 'Check-out date must be after check-in date'})
        
        # Check availability
        days_needed = (check_out_date - check_in_date).days
        available_room_type = next(
            (
                room_type
                for room_type in hotel.room_types.filter(is_active=True)
                if room_type.availability.filter(
                    date__gte=check_in_date,
                    date__lt=check_out_date,
                    available_rooms__gt=0,
                ).count() == days_needed
            ),
            None,
        )

        if available_room_type:
            availability = available_room_type.availability.filter(
                date__gte=check_in_date,
                date__lt=check_out_date,
                available_rooms__gt=0,
            ).order_by('date')
            total_price = sum(av.price_per_night.amount for av in availability)
            return JsonResponse({
                'available': True,
                'total_price': total_price,
                'nights': days_needed,
                'price_per_night': total_price / days_needed if days_needed > 0 else 0,
            })
        else:
            return JsonResponse({
                'available': False,
                'message': 'Hotel is not available for the selected dates'
            })
    
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'})


def add_to_wishlist(request, hotel_id):
    """Add hotel to wishlist"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to add items to wishlist.')
        return redirect('account_login')
    
    hotel = get_object_or_404(Hotel, id=hotel_id, is_active=True)
    
    from django.contrib.contenttypes.models import ContentType
    from users.models import WishlistItem
    
    content_type = ContentType.objects.get_for_model(Hotel)
    
    wishlist_item, created = WishlistItem.objects.get_or_create(
        user=request.user,
        content_type=content_type,
        object_id=hotel.id
    )
    
    if created:
        messages.success(request, f'{hotel.name} added to your wishlist!')
    else:
        messages.info(request, f'{hotel.name} is already in your wishlist.')
    
    return redirect('hotels:hotel_detail', hotel_id=hotel.id)
