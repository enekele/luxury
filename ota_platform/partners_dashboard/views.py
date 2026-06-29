from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import logging
import json

from affiliates.models import AffiliateProfile 
from hotels.models import Hotel
from bookings.models import Booking
from cars.models import CarRental
from flights.models import Flight
from tours.models import Tour

logger = logging.getLogger(__name__)


@login_required
def partners_dashboard(request):
    """
    Partner dashboard: shows partner's affiliate profile, facilities and recent reservations.
    """
    # Try to get affiliate profile for the current user (partners are affiliates in this setup)
    try:
        affiliate_profile = request.user.affiliate_profile
    except AffiliateProfile.DoesNotExist:
        affiliate_profile = None

    # Determine hotels and other services linked to the current user's Partner account
    hotels = Hotel.objects.filter(partner__partner_profile__user=request.user).order_by('-id')
    flights = Flight.objects.filter(partner_profile__user=request.user).order_by('-id')
    cars = CarRental.objects.filter(partner_profile__user=request.user).order_by('-id')
    tours = Tour.objects.filter(partner_profile__user=request.user).order_by('-id')

    hotel_ct = ContentType.objects.get_for_model(Hotel)
    flight_ct = ContentType.objects.get_for_model(Flight)
    car_ct = ContentType.objects.get_for_model(CarRental)
    tour_ct = ContentType.objects.get_for_model(Tour)

    hotel_ids = list(hotels.values_list('id', flat=True))
    flight_ids = list(flights.values_list('id', flat=True))
    car_ids = list(cars.values_list('id', flat=True))
    tour_ids = list(tours.values_list('id', flat=True))

    bookings_qs = Booking.objects.filter(
        Q(content_type=hotel_ct, object_id__in=hotel_ids) |
        Q(content_type=flight_ct, object_id__in=flight_ids) |
        Q(content_type=car_ct, object_id__in=car_ids) |
        Q(content_type=tour_ct, object_id__in=tour_ids)
    )

    bookings_count = bookings_qs.count()
    bookings = bookings_qs.order_by('-created_at')[:50]

    # Calculate chart data: bookings per day for last 30 days
    today = timezone.now().date()
    thirty_days_ago = today - timedelta(days=30)
    
    daily_bookings = {}
    for i in range(30):
        date = today - timedelta(days=30-i)
        daily_bookings[date.isoformat()] = 0
    
    bookings_30days = bookings_qs.filter(created_at__date__gte=thirty_days_ago)
    for booking in bookings_30days:
        booking_date = booking.created_at.date().isoformat()
        if booking_date in daily_bookings:
            daily_bookings[booking_date] += 1
    
    bookings_dates = list(daily_bookings.keys())
    bookings_counts = list(daily_bookings.values())

    booking_amounts = [booking.total_amount.amount for booking in bookings_30days if booking.total_amount]
    total_revenue = sum(booking_amounts)
    confirmed_bookings = bookings_qs.filter(status='confirmed').count()
    pending_bookings = bookings_qs.filter(status='pending').count()
    cancelled_bookings = bookings_qs.filter(status='cancelled').count()
    active_hotels = hotels.filter(is_available=True).count()

    room_capacity = sum(
        room_type.total_rooms
        for hotel in hotels
        for room_type in hotel.room_types.all()
    )
    room_capacity = max(room_capacity, 1)

    occupancy_rate = round(
        min(100, (bookings_30days.count() / room_capacity) * 100),
        1
    ) if bookings_30days.count() else 0
    adr = round(total_revenue / confirmed_bookings, 2) if confirmed_bookings else 0
    revpar = round(total_revenue / room_capacity, 2) if room_capacity else 0

    revenue_str = f"${total_revenue:,.2f}"
    occupancy_rate_str = f"{occupancy_rate:.1f}%"
    adr_str = f"${adr:,.2f}"
    revpar_str = f"${revpar:,.2f}"

    module_sections = [
        {
            'title': 'Core Management Modules',
            'icon': 'fas fa-cubes',
            'items': [
                'Real-time room allocation and seat mapping',
                'Fleet tracking and bulk availability updates',
                'Multi-currency pricing and tax configuration'
            ],
        },
        {
            'title': 'Booking & Reservations',
            'icon': 'fas fa-calendar-check',
            'items': [
                'Centralized booking feed and live confirmation statuses',
                'Cancellation processing and modification logs',
                'Instant alerts for overbooking risks'
            ],
        },
        {
            'title': 'Financial & Analytics',
            'icon': 'fas fa-chart-pie',
            'items': [
                'Automated commission splitting and payout logs',
                'Occupancy, ADR, RevPAR and conversion insights',
                'Competitive market and forecasting benchmarks'
            ],
        },
        {
            'title': 'Engagement & Support',
            'icon': 'fas fa-headset',
            'items': [
                'Image uploads, amenity checklists and multilingual editors',
                'Guest feedback streams and sentiment insights',
                'Marketing campaigns, loyalty tools and helpdesk tickets'
            ],
        },
    ]

    context = {
        'affiliate_profile': affiliate_profile,
        'hotels': hotels,
        'bookings': bookings,
        'flights': flights,
        'cars': cars,
        'tours': tours,
        'bookings_count': bookings_count,
        'hotel_count': hotels.count(),
        'flight_count': flights.count(),
        'car_count': cars.count(),
        'tour_count': tours.count(),
        'active_hotels': active_hotels,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'cancelled_bookings': cancelled_bookings,
        'bookings_dates': json.dumps(bookings_dates),
        'bookings_counts': json.dumps(bookings_counts),
        'revenue': revenue_str,
        'occupancy_rate': occupancy_rate_str,
        'adr': adr_str,
        'revpar': revpar_str,
        'pending_issues': pending_bookings,
        'module_sections': module_sections,
    }
    return render(request, "partners_dashboard/dashboard.html", context)


@login_required
@require_POST
def toggle_availability(request):
    hotel_id = request.POST.get('hotel_id')
    if not hotel_id:
        return HttpResponseBadRequest("Missing hotel_id")

    hotel = get_object_or_404(Hotel, id=hotel_id)

    # authorization: only owner on the HotelPartner can toggle
    partner = getattr(hotel, 'partner', None)
    if not (partner and getattr(partner, 'owner', None) == request.user):
        return HttpResponseForbidden("Not allowed")

    hotel.is_active = not bool(hotel.is_active)
    hotel.save(update_fields=['is_active'])
    return JsonResponse({'status': 'ok', 'is_active': hotel.is_active, 'hotel_id': hotel.id})


@login_required
@require_POST
def confirm_reservation(request):
    booking_id = request.POST.get('booking_id')
    action = request.POST.get('action')
    if not booking_id or action not in ('confirm', 'cancel'):
        return HttpResponseBadRequest("Invalid params")

    booking = get_object_or_404(Booking, id=booking_id)

    hotel = getattr(booking, 'hotel', None)
    partner = getattr(hotel, 'partner', None)
    if not (hotel and partner and getattr(partner, 'owner', None) == request.user):
        return HttpResponseForbidden("Not allowed")

    with transaction.atomic():
        if hasattr(booking, 'status'):
            booking.status = 'confirmed' if action == 'confirm' else 'cancelled'
        elif hasattr(booking, 'confirmed'):
            booking.confirmed = (action == 'confirm')
        else:
            try:
                booking.gateway_response = booking.gateway_response or {}
                booking.gateway_response['partner_action'] = action
            except Exception:
                pass
        booking.save()
    return JsonResponse({'status': 'ok', 'booking_id': booking.id, 'action': action})
