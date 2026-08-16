from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import redirect, render, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta, datetime
import logging
import json

from djmoney.money import Money

from affiliates.models import AffiliateProfile 
from hotels.models import Hotel, HotelPartner
from bookings.models import Booking
from cars.models import CarBrand, CarRental, CarModel, CarRentalCompany
from flights.models import Flight, Airline, Airport
from tours.models import Tour, TourCategory, TourOperator
from core.models import Country
from core.models import City
from partners_dashboard.models import Partner

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
    thirty_days_ago = today - timedelta(days=29)
    
    daily_bookings = {}
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
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


def get_partner_profile_for_user(user):
    partner = getattr(user, 'partner_profile', None)
    if partner:
        return partner
    partner_name = user.get_full_name() or user.email.split('@')[0]
    return Partner.objects.create(user=user, company_name=partner_name)


@login_required
def manage_properties(request):
    """List the partner's managed properties and allow quick updates."""
    hotels = Hotel.objects.filter(partner__owner=request.user).order_by('-updated_at')
    flights = Flight.objects.filter(partner_profile__user=request.user).order_by('-updated_at')
    cars = CarRental.objects.filter(partner_profile__user=request.user).order_by('-updated_at')
    tours = Tour.objects.filter(partner_profile__user=request.user).order_by('-updated_at')

    properties = [
        {'type': 'Hotel', 'label': 'Hotel', 'items': hotels, 'link_name': 'partners_dashboard:update_hotel_property', 'create_url': 'partners_dashboard:create_hotel_property'},
        {'type': 'Flight', 'label': 'Flight', 'items': flights, 'link_name': 'partners_dashboard:update_flight_property', 'create_url': 'partners_dashboard:create_flight_property'},
        {'type': 'Car', 'label': 'Car rental', 'items': cars, 'link_name': 'partners_dashboard:update_car_property', 'create_url': 'partners_dashboard:create_car_property'},
        {'type': 'Tour', 'label': 'Tour', 'items': tours, 'link_name': 'partners_dashboard:update_tour_property', 'create_url': 'partners_dashboard:create_tour_property'},
    ]

    context = {
        'properties': properties,
        'hotel_count': hotels.count(),
        'flight_count': flights.count(),
        'car_count': cars.count(),
        'tour_count': tours.count(),
        'property_count': sum(item['items'].count() for item in properties),
    }
    return render(request, 'partners_dashboard/manage_properties.html', context)


@login_required
def create_hotel_property(request):
    partner = get_partner_profile_for_user(request.user)
    if request.method == 'POST':
        country_id = request.POST.get('country')
        city_id = request.POST.get('city')
        country = get_object_or_404(Country, id=country_id)
        city = get_object_or_404(City, id=city_id, country=country)

        with transaction.atomic():
            hotel = Hotel.objects.create(
                name=request.POST.get('name', '').strip(),
                description=request.POST.get('description', '').strip(),
                city=city,
                address=request.POST.get('address', '').strip(),
                star_rating=int(request.POST.get('star_rating', 3) or 3),
                is_available=request.POST.get('is_available') == 'on',
                is_featured=request.POST.get('is_featured') == 'on',
            )
            price_amount = request.POST.get('price_per_night_0')
            if price_amount:
                price_currency = request.POST.get('price_per_night_1', 'USD')
                hotel.price_per_night = Money(Decimal(str(price_amount)), price_currency)
            if 'main_image' in request.FILES:
                hotel.main_image = request.FILES['main_image']
            hotel.save()

            HotelPartner.objects.create(
                owner=request.user,
                hotel=hotel,
                partner_name=partner.company_name or request.user.get_full_name() or 'Partner',
                partner_id=f"HP-{hotel.id}",
                partner_profile=partner,
            )
        messages.success(request, f'{hotel.name} was added successfully.')
        return redirect('partners_dashboard:manage_properties')

    countries = Country.objects.all().order_by('name')
    cities = City.objects.filter(is_active=True).select_related('country').order_by('name')
    context = {'countries': countries, 'cities': cities}
    return render(request, 'partners_dashboard/create_hotel_property.html', context)


@login_required
def create_flight_property(request):
    partner = get_partner_profile_for_user(request.user)
    if request.method == 'POST':
        airline_id = request.POST.get('airline')
        origin_id = request.POST.get('origin')
        destination_id = request.POST.get('destination')
        airline = get_object_or_404(Airline, id=airline_id)
        origin = get_object_or_404(Airport, id=origin_id)
        destination = get_object_or_404(Airport, id=destination_id)

        departure = request.POST.get('departure_time')
        arrival = request.POST.get('arrival_time')
        departure_dt = datetime.strptime(departure, '%Y-%m-%dT%H:%M') if departure else timezone.now()
        arrival_dt = datetime.strptime(arrival, '%Y-%m-%dT%H:%M') if arrival else departure_dt + timedelta(hours=2)

        flight = Flight.objects.create(
            airline=airline,
            flight_number=request.POST.get('flight_number', '').strip(),
            origin=origin,
            destination=destination,
            departure_time=departure_dt,
            arrival_time=arrival_dt,
            duration=arrival_dt - departure_dt,
            total_seats=int(request.POST.get('total_seats', 180) or 180),
            available_seats=int(request.POST.get('available_seats', 180) or 180),
            status=request.POST.get('status', 'scheduled'),
            partner_profile=partner,
        )
        price_amount = request.POST.get('economy_price_0')
        if price_amount:
            currency = request.POST.get('economy_price_1', 'USD')
            flight.economy_price = Money(Decimal(str(price_amount)), currency)
        # Handle image upload
        if 'main_image' in request.FILES:
            flight.main_image = request.FILES['main_image']
        flight.save()
        messages.success(request, f'{flight.flight_number} was added successfully.')
        return redirect('partners_dashboard:manage_properties')

    airlines = Airline.objects.all()
    airports = Airport.objects.all()
    return render(request, 'partners_dashboard/create_flight_property.html', {'airlines': airlines, 'airports': airports})


@login_required
def create_car_property(request):
    partner = get_partner_profile_for_user(request.user)
    if request.method == 'POST':
        city_id = request.POST.get('city')
        car_model_id = request.POST.get('car_model')
        company_id = request.POST.get('company')
        city = get_object_or_404(City, id=city_id)
        car_model = get_object_or_404(CarModel, id=car_model_id)
        company = get_object_or_404(CarRentalCompany, id=company_id)

        car = CarRental.objects.create(
            company=company,
            car_model=car_model,
            city=city,
            pickup_location=request.POST.get('pickup_location', '').strip(),
            pickup_address=request.POST.get('pickup_address', ''),
            year=int(request.POST.get('year', timezone.now().year) or timezone.now().year),
            category=request.POST.get('category', 'economy'),
            passengers=int(request.POST.get('passengers', 4) or 4),
            bags=int(request.POST.get('bags', 2) or 2),
            doors=int(request.POST.get('doors', 4) or 4),
            transmission=request.POST.get('transmission', 'automatic'),
            fuel_type=request.POST.get('fuel_type', 'gasoline'),
            is_available=request.POST.get('is_available') == 'on',
            partner_profile=partner,
        )
        daily_price = request.POST.get('price_per_day_0')
        if daily_price:
            currency = request.POST.get('price_per_day_1', 'USD')
            car.price_per_day = Money(Decimal(str(daily_price)), currency)
        deposit = request.POST.get('security_deposit_0')
        if deposit:
            deposit_currency = request.POST.get('security_deposit_1', 'USD')
            car.security_deposit = Money(Decimal(str(deposit)), deposit_currency)
        # Handle image upload
        if 'main_image' in request.FILES:
            car.main_image = request.FILES['main_image']
        car.save()
        messages.success(request, f'{car.car_model} was added successfully.')
        return redirect('partners_dashboard:manage_properties')

    cities = City.objects.filter(is_active=True)
    car_models = CarModel.objects.all()
    companies = CarRentalCompany.objects.all()
    return render(request, 'partners_dashboard/create_car_property.html', {'cities': cities, 'car_models': car_models, 'companies': companies})


@login_required
def create_tour_property(request):
    partner = get_partner_profile_for_user(request.user)
    if request.method == 'POST':
        operator_id = request.POST.get('operator')
        category_id = request.POST.get('category')
        destination_id = request.POST.get('destination')
        operator = get_object_or_404(TourOperator, id=operator_id)
        category = get_object_or_404(TourCategory, id=category_id)
        destination = get_object_or_404(City, id=destination_id)

        start_time = request.POST.get('start_time') or '08:00:00'
        end_time = request.POST.get('end_time') or '16:00:00'

        tour = Tour.objects.create(
            operator=operator,
            category=category,
            name=request.POST.get('name', '').strip(),
            description=request.POST.get('description', ''),
            highlights=request.POST.get('highlights', ''),
            destination=destination,
            meeting_point=request.POST.get('meeting_point', '').strip(),
            meeting_address=request.POST.get('meeting_address', ''),
            duration_days=int(request.POST.get('duration_days', 1) or 1),
            duration_hours=int(request.POST.get('duration_hours', 8) or 8),
            price_per_person='0.00',
            max_participants=int(request.POST.get('max_participants', 15) or 15),
            min_participants=int(request.POST.get('min_participants', 1) or 1),
            start_time=start_time,
            end_time=end_time,
            is_available=request.POST.get('is_available') == 'on',
            partner_profile=partner,
        )
        price_amount = request.POST.get('price_per_person_0')
        if price_amount:
            currency = request.POST.get('price_per_person_1', 'USD')
            tour.price_per_person = Money(Decimal(str(price_amount)), currency)
        # Handle image upload
        if 'main_image' in request.FILES:
            tour.main_image = request.FILES['main_image']
        tour.save()
        messages.success(request, f'{tour.name} was added successfully.')
        return redirect('partners_dashboard:manage_properties')

    operators = TourOperator.objects.all()
    categories = TourCategory.objects.all()
    cities = City.objects.filter(is_active=True)
    return render(request, 'partners_dashboard/create_tour_property.html', {'operators': operators, 'categories': categories, 'cities': cities})


@login_required
def update_property(request, hotel_id):
    """Compatibility route for the legacy hotel update page."""
    return update_hotel_property(request, hotel_id)


@login_required
def update_hotel_property(request, hotel_id):
    """Update a partner-owned hotel property."""
    hotel = get_object_or_404(Hotel, id=hotel_id)
    if not getattr(hotel, 'partner', None) or hotel.partner.owner != request.user:
        return HttpResponseForbidden('You do not have permission to manage this property.')

    if request.method == 'POST':
        hotel.name = request.POST.get('name', hotel.name).strip()
        hotel.description = request.POST.get('description', hotel.description)
        hotel.address = request.POST.get('address', hotel.address)
        hotel.star_rating = int(request.POST.get('star_rating', hotel.star_rating) or hotel.star_rating)

        price_amount = request.POST.get('price_per_night_0')
        if price_amount:
            price_currency = request.POST.get('price_per_night_1', str(hotel.price_per_night.currency))
            try:
                hotel.price_per_night = Money(Decimal(str(price_amount)), price_currency)
            except Exception:
                hotel.price_per_night = Money(Decimal(str(hotel.price_per_night.amount)), str(hotel.price_per_night.currency))

        hotel.is_available = request.POST.get('is_available') == 'on'
        hotel.is_featured = request.POST.get('is_featured') == 'on'
        hotel.save()
        messages.success(request, f'{hotel.name} has been updated successfully.')
        return redirect('partners_dashboard:manage_properties')

    context = {'property': hotel, 'property_type': 'Hotel'}
    return render(request, 'partners_dashboard/update_property.html', context)


@login_required
def update_flight_property(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    if flight.partner_profile is None or flight.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to manage this property.')

    if request.method == 'POST':
        flight.flight_number = request.POST.get('flight_number', flight.flight_number).strip()
        flight.status = request.POST.get('status', flight.status)
        flight.available_seats = int(request.POST.get('available_seats', flight.available_seats) or flight.available_seats)

        price_amount = request.POST.get('economy_price_0')
        if price_amount:
            price_currency = request.POST.get('economy_price_1', str(flight.economy_price.currency))
            try:
                flight.economy_price = Money(Decimal(str(price_amount)), price_currency)
            except Exception:
                flight.economy_price = Money(Decimal(str(flight.economy_price.amount)), str(flight.economy_price.currency))

        flight.save()
        messages.success(request, f'{flight.flight_number} has been updated successfully.')
        return redirect('partners_dashboard:manage_properties')

    context = {'property': flight, 'property_type': 'Flight'}
    return render(request, 'partners_dashboard/update_flight_property.html', context)


@login_required
def update_car_property(request, car_id):
    car = get_object_or_404(CarRental, id=car_id)
    if car.partner_profile is None or car.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to manage this property.')

    if request.method == 'POST':
        car.pickup_location = request.POST.get('pickup_location', car.pickup_location).strip()
        car.is_available = request.POST.get('is_available') == 'on'

        price_amount = request.POST.get('price_per_day_0')
        if price_amount:
            price_currency = request.POST.get('price_per_day_1', str(car.price_per_day.currency))
            try:
                car.price_per_day = Money(Decimal(str(price_amount)), price_currency)
            except Exception:
                car.price_per_day = Money(Decimal(str(car.price_per_day.amount)), str(car.price_per_day.currency))

        car.save()
        messages.success(request, f'{car.car_model} has been updated successfully.')
        return redirect('partners_dashboard:manage_properties')

    context = {'property': car, 'property_type': 'Car rental'}
    return render(request, 'partners_dashboard/update_car_property.html', context)


@login_required
def update_tour_property(request, tour_id):
    tour = get_object_or_404(Tour, id=tour_id)
    if tour.partner_profile is None or tour.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to manage this property.')

    if request.method == 'POST':
        tour.name = request.POST.get('name', tour.name).strip()
        tour.description = request.POST.get('description', tour.description)
        tour.meeting_point = request.POST.get('meeting_point', tour.meeting_point).strip()
        tour.is_available = request.POST.get('is_available') == 'on'

        price_amount = request.POST.get('price_per_person_0')
        if price_amount:
            price_currency = request.POST.get('price_per_person_1', str(tour.price_per_person.currency))
            try:
                tour.price_per_person = Money(Decimal(str(price_amount)), price_currency)
            except Exception:
                tour.price_per_person = Money(Decimal(str(tour.price_per_person.amount)), str(tour.price_per_person.currency))

        tour.save()
        messages.success(request, f'{tour.name} has been updated successfully.')
        return redirect('partners_dashboard:manage_properties')

    context = {'property': tour, 'property_type': 'Tour'}
    return render(request, 'partners_dashboard/update_tour_property.html', context)


@login_required
def checkout_hotel_property(request, hotel_id):
    hotel = get_object_or_404(Hotel, id=hotel_id)
    if getattr(hotel, 'partner', None) is None or hotel.partner.owner != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': hotel, 'property_type': 'Hotel'}
    return render(request, 'partners_dashboard/checkout_hotel_property.html', context)


@login_required
def checkout_flight_property(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    if flight.partner_profile is None or flight.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': flight, 'property_type': 'Flight'}
    return render(request, 'partners_dashboard/checkout_flight_property.html', context)


@login_required
def checkout_car_property(request, car_id):
    car = get_object_or_404(CarRental, id=car_id)
    if car.partner_profile is None or car.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': car, 'property_type': 'Car rental'}
    return render(request, 'partners_dashboard/checkout_car_property.html', context)


@login_required
def checkout_tour_property(request, tour_id):
    tour = get_object_or_404(Tour, id=tour_id)
    if tour.partner_profile is None or tour.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': tour, 'property_type': 'Tour'}
    return render(request, 'partners_dashboard/checkout_tour_property.html', context)


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

    hotel.is_available = not bool(hotel.is_available)
    hotel.save(update_fields=['is_available'])
    return JsonResponse({
        'status': 'ok',
        'is_available': hotel.is_available,
        'hotel_id': hotel.id,
    })


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