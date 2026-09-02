import csv
import json
from decimal import Decimal
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from djmoney.money import Money

from affiliates.models import AffiliateProfile 
from hotels.models import Hotel, HotelPartner
from bookings.models import Booking
from cars.models import CarBrand, CarRental, CarModel, CarRentalCompany
from flights.models import Flight, Airline, Airport
from tours.models import Tour, TourCategory, TourOperator
from core.models import City, Country
from partners_dashboard.decorators import partner_required
from partners_dashboard.forms import CityForm, CountryForm


BOOKING_STATUS_ACTIONS = {
    'pending': {
        'confirm': 'confirmed',
        'cancel': 'cancelled',
    },
    'confirmed': {
        'complete': 'completed',
        'cancel': 'cancelled',
    },
    'cancelled': {},
    'completed': {},
}


def partner_inventory(request_user):
    """Return the four inventory querysets owned by a partner user."""
    return {
        'hotels': Hotel.objects.filter(
            partner__partner_profile__user=request_user
        ),
        'flights': Flight.objects.filter(partner_profile__user=request_user),
        'cars': CarRental.objects.filter(partner_profile__user=request_user),
        'tours': Tour.objects.filter(partner_profile__user=request_user),
    }


def partner_bookings(request_user):
    """Return bookings whose generic service object belongs to the partner."""
    inventory = partner_inventory(request_user)
    content_types = ContentType.objects.get_for_models(
        Hotel,
        Flight,
        CarRental,
        Tour,
    )

    owned_services = (
        Q(
            content_type=content_types[Hotel],
            object_id__in=inventory['hotels'].values('id'),
        )
        | Q(
            content_type=content_types[Flight],
            object_id__in=inventory['flights'].values('id'),
        )
        | Q(
            content_type=content_types[CarRental],
            object_id__in=inventory['cars'].values('id'),
        )
        | Q(
            content_type=content_types[Tour],
            object_id__in=inventory['tours'].values('id'),
        )
    )

    return Booking.objects.filter(owned_services).select_related(
        'user',
        'content_type',
    )


def owned_property(request_user, service_type, property_id):
    """Resolve one partner-owned service without exposing another partner's IDs."""
    inventory = partner_inventory(request_user)
    querysets = {
        'hotel': inventory['hotels'],
        'flight': inventory['flights'],
        'car': inventory['cars'],
        'tour': inventory['tours'],
    }
    queryset = querysets.get(service_type)
    if queryset is None:
        raise Http404('Unsupported property type.')
    return get_object_or_404(queryset, id=property_id)


def apply_booking_filters(queryset, request):
    status = request.GET.get('status', '').strip()
    service = request.GET.get('service', '').strip()
    search_query = request.GET.get('q', '').strip()

    valid_statuses = {choice[0] for choice in Booking._meta.get_field('status').choices}
    service_models = {
        'hotel': 'hotel',
        'flight': 'flight',
        'car': 'carrental',
        'tour': 'tour',
    }

    if status in valid_statuses:
        queryset = queryset.filter(status=status)
    else:
        status = ''

    if service in service_models:
        queryset = queryset.filter(content_type__model=service_models[service])
    else:
        service = ''

    if search_query:
        queryset = queryset.filter(
            Q(booking_reference__icontains=search_query)
            | Q(contact_name__icontains=search_query)
            | Q(contact_email__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    return queryset, status, service, search_query


def change_booking_status(booking, action):
    target_status = BOOKING_STATUS_ACTIONS.get(booking.status, {}).get(action)
    if target_status is None:
        action_labels = {
            'confirm': 'confirmed',
            'cancel': 'cancelled',
            'complete': 'completed',
        }
        action_label = action_labels.get(action, 'updated with that action')
        return False, (
            f'{booking.get_status_display()} reservations cannot be {action_label}.'
        )

    booking.status = target_status
    booking.save(update_fields=['status', 'updated_at'])
    return True, f'Reservation {booking.booking_reference} is now {booking.get_status_display().lower()}.'


@partner_required
def partners_dashboard(request):
    """
    Partner dashboard: shows partner's affiliate profile, facilities and recent reservations.
    """
    # Try to get affiliate profile for the current user (partners are affiliates in this setup)
    try:
        affiliate_profile = request.user.affiliate_profile
    except AffiliateProfile.DoesNotExist:
        affiliate_profile = None

    inventory = partner_inventory(request.user)
    hotels = inventory['hotels'].order_by('-id')
    flights = inventory['flights'].order_by('-id')
    cars = inventory['cars'].order_by('-id')
    tours = inventory['tours'].order_by('-id')
    bookings_qs = partner_bookings(request.user)

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

    revenue_bookings = bookings_30days.filter(status__in=['confirmed', 'completed'])
    revenue_by_currency = {}
    for booking in revenue_bookings:
        if not booking.total_amount:
            continue
        currency = str(booking.total_amount.currency)
        revenue_by_currency[currency] = (
            revenue_by_currency.get(currency, Decimal('0'))
            + booking.total_amount.amount
        )

    revenue_str = ' · '.join(
        f'{currency} {amount:,.2f}'
        for currency, amount in sorted(revenue_by_currency.items())
    ) or 'USD 0.00'
    confirmed_bookings = bookings_qs.filter(status='confirmed').count()
    pending_bookings = bookings_qs.filter(status='pending').count()
    cancelled_bookings = bookings_qs.filter(status='cancelled').count()
    completed_bookings = bookings_qs.filter(status='completed').count()
    active_properties = (
        hotels.filter(is_available=True).count()
        + flights.filter(status='scheduled', available_seats__gt=0).count()
        + cars.filter(is_available=True).count()
        + tours.filter(is_available=True).count()
    )

    module_sections = [
        {
            'title': 'Core Management Modules',
            'icon': 'fas fa-cubes',
            'items': [
                'Create and edit hotels, flights, cars, and tours',
                'Open or close inventory for new reservations',
                'Maintain country and city destination data'
            ],
        },
        {
            'title': 'Booking & Reservations',
            'icon': 'fas fa-calendar-check',
            'items': [
                'Review partner-owned reservations in one queue',
                'Confirm, cancel, or complete valid reservations',
                'View customer contact details and special requests'
            ],
        },
        {
            'title': 'Financial & Analytics',
            'icon': 'fas fa-chart-pie',
            'items': [
                'Track confirmed revenue and booking volume',
                'Monitor pending and cancelled reservations',
                'Export reservation records as CSV'
            ],
        },
        {
            'title': 'Engagement & Support',
            'icon': 'fas fa-headset',
            'items': [
                'Preview partner listings before customer checkout',
                'See inventory and booking status at a glance',
                'Keep inactive partner accounts out of operations'
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
        'active_properties': active_properties,
        'confirmed_bookings': confirmed_bookings,
        'pending_bookings': pending_bookings,
        'cancelled_bookings': cancelled_bookings,
        'completed_bookings': completed_bookings,
        'bookings_30days_count': bookings_30days.count(),
        'bookings_dates': json.dumps(bookings_dates),
        'bookings_counts': json.dumps(bookings_counts),
        'revenue': revenue_str,
        'module_sections': module_sections,
    }
    return render(request, "partners_dashboard/dashboard.html", context)


def get_partner_profile_for_user(user):
    return user.partner_profile


@partner_required
def manage_properties(request):
    """List the partner's managed properties and allow quick updates."""
    inventory = partner_inventory(request.user)
    hotels = inventory['hotels'].order_by('-updated_at')
    flights = inventory['flights'].order_by('-updated_at')
    cars = inventory['cars'].order_by('-updated_at')
    tours = inventory['tours'].order_by('-updated_at')

    properties = [
        {
            'type': 'Hotel',
            'slug': 'hotel',
            'label': 'Hotel',
            'items': hotels,
            'available_count': hotels.filter(is_available=True).count(),
            'link_name': 'partners_dashboard:update_hotel_property',
            'create_url': 'partners_dashboard:create_hotel_property',
            'checkout_url': 'partners_dashboard:checkout_hotel_property',
        },
        {
            'type': 'Flight',
            'slug': 'flight',
            'label': 'Flight',
            'items': flights,
            'available_count': flights.filter(
                status='scheduled', available_seats__gt=0
            ).count(),
            'link_name': 'partners_dashboard:update_flight_property',
            'create_url': 'partners_dashboard:create_flight_property',
            'checkout_url': 'partners_dashboard:checkout_flight_property',
        },
        {
            'type': 'Car',
            'slug': 'car',
            'label': 'Car rental',
            'items': cars,
            'available_count': cars.filter(is_available=True).count(),
            'link_name': 'partners_dashboard:update_car_property',
            'create_url': 'partners_dashboard:create_car_property',
            'checkout_url': 'partners_dashboard:checkout_car_property',
        },
        {
            'type': 'Tour',
            'slug': 'tour',
            'label': 'Tour',
            'items': tours,
            'available_count': tours.filter(is_available=True).count(),
            'link_name': 'partners_dashboard:update_tour_property',
            'create_url': 'partners_dashboard:create_tour_property',
            'checkout_url': 'partners_dashboard:checkout_tour_property',
        },
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


@partner_required
def manage_reservations(request):
    """Search, filter, and manage reservations for the partner's inventory."""
    base_queryset = partner_bookings(request.user)
    filtered_queryset, status, service, search_query = apply_booking_filters(
        base_queryset,
        request,
    )
    paginator = Paginator(filtered_queryset.order_by('-created_at'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'bookings': page_obj,
        'page_obj': page_obj,
        'selected_status': status,
        'selected_service': service,
        'search_query': search_query,
        'status_choices': Booking._meta.get_field('status').choices,
        'total_count': base_queryset.count(),
        'pending_count': base_queryset.filter(status='pending').count(),
        'confirmed_count': base_queryset.filter(status='confirmed').count(),
        'completed_count': base_queryset.filter(status='completed').count(),
    }
    return render(request, 'partners_dashboard/manage_reservations.html', context)


@partner_required
def reservation_detail(request, booking_id):
    booking = get_object_or_404(partner_bookings(request.user), id=booking_id)
    allowed_actions = BOOKING_STATUS_ACTIONS.get(booking.status, {})
    return render(
        request,
        'partners_dashboard/reservation_detail.html',
        {
            'booking': booking,
            'allowed_actions': allowed_actions,
        },
    )


@partner_required
@require_POST
def update_reservation_status(request, booking_id):
    action = request.POST.get('action', '').strip()

    with transaction.atomic():
        booking = get_object_or_404(
            partner_bookings(request.user).select_for_update(),
            id=booking_id,
        )
        changed, message = change_booking_status(booking, action)

    if changed:
        messages.success(request, message)
    else:
        messages.error(request, message)

    if request.POST.get('return_to') == 'reservations':
        return redirect('partners_dashboard:manage_reservations')
    if request.POST.get('return_to') == 'dashboard':
        return redirect('partners_dashboard:partners_dashboard')
    return redirect('partners_dashboard:reservation_detail', booking_id=booking.id)


@partner_required
def export_reservations(request):
    queryset, _, _, _ = apply_booking_filters(
        partner_bookings(request.user).order_by('-created_at'),
        request,
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="partner-reservations.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            'Reference',
            'Service type',
            'Service',
            'Customer',
            'Customer email',
            'Booking date',
            'Check in',
            'Check out',
            'Quantity',
            'Amount',
            'Currency',
            'Reservation status',
            'Payment status',
            'Created at',
        ]
    )
    for booking in queryset:
        service = booking.content_object
        writer.writerow(
            [
                booking.booking_reference,
                booking.content_type.model,
                str(service) if service else '',
                booking.contact_name,
                booking.contact_email,
                booking.booking_date.isoformat() if booking.booking_date else '',
                booking.check_in.isoformat() if booking.check_in else '',
                booking.check_out.isoformat() if booking.check_out else '',
                booking.quantity,
                booking.total_amount.amount,
                booking.total_amount.currency,
                booking.status,
                booking.payment_status,
                booking.created_at.isoformat(),
            ]
        )

    return response


@partner_required
def manage_locations(request):
    """Allow active partners to add countries and cities used by properties."""
    country_form = CountryForm(prefix='country')
    city_form = CityForm(prefix='city')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_country':
            country_form = CountryForm(request.POST, prefix='country')
            if country_form.is_valid():
                country = country_form.save()
                messages.success(request, f'{country.name} was added successfully.')
                return redirect('partners_dashboard:manage_locations')
        elif action == 'add_city':
            city_form = CityForm(request.POST, prefix='city')
            if city_form.is_valid():
                city = city_form.save()
                messages.success(request, f'{city} was added successfully.')
                return redirect('partners_dashboard:manage_locations')
        else:
            messages.error(request, 'Choose whether you are adding a country or a city.')

    countries = Country.objects.select_related('currency').annotate(
        city_count=Count('cities')
    ).order_by('name')
    cities = City.objects.select_related('country').order_by('country__name', 'name')

    context = {
        'country_form': country_form,
        'city_form': city_form,
        'countries': countries,
        'cities': cities,
        'has_active_countries': Country.objects.filter(is_active=True).exists(),
    }
    return render(request, 'partners_dashboard/manage_locations.html', context)


@partner_required
def create_hotel_property(request):
    partner = get_partner_profile_for_user(request.user)
    if request.method == 'POST':
        country_id = request.POST.get('country')
        city_id = request.POST.get('city')
        country = get_object_or_404(Country, id=country_id)
        city = get_object_or_404(City, id=city_id, country=country)
        price_amount = request.POST.get('price_per_night_0') or '0'
        price_currency = request.POST.get('price_per_night_1', 'USD')

        with transaction.atomic():
            hotel = Hotel.objects.create(
                name=request.POST.get('name', '').strip(),
                description=request.POST.get('description', '').strip(),
                city=city,
                address=request.POST.get('address', '').strip(),
                star_rating=int(request.POST.get('star_rating', 3) or 3),
                price_per_night=Money(Decimal(str(price_amount)), price_currency),
                is_available=request.POST.get('is_available') == 'on',
                is_featured=request.POST.get('is_featured') == 'on',
            )
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


@partner_required
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


@partner_required
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


@partner_required
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


@partner_required
def update_property(request, hotel_id):
    """Compatibility route for the legacy hotel update page."""
    return update_hotel_property(request, hotel_id)


@partner_required
def cities_for_country(request):
    country_id = request.GET.get('country_id')

    if not country_id:
        return JsonResponse({'cities': []})

    cities = City.objects.filter(
        country_id=country_id,
        country__is_active=True,
        is_active=True,
    ).order_by('name').values('id', 'name')

    return JsonResponse({'cities': list(cities)})


@partner_required
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


@partner_required
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


@partner_required
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


@partner_required
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


@partner_required
def checkout_hotel_property(request, hotel_id):
    hotel = get_object_or_404(Hotel, id=hotel_id)
    if getattr(hotel, 'partner', None) is None or hotel.partner.owner != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': hotel, 'property_type': 'Hotel'}
    return render(request, 'partners_dashboard/checkout_hotel_property.html', context)


@partner_required
def checkout_flight_property(request, flight_id):
    flight = get_object_or_404(Flight, id=flight_id)
    if flight.partner_profile is None or flight.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': flight, 'property_type': 'Flight'}
    return render(request, 'partners_dashboard/checkout_flight_property.html', context)


@partner_required
def checkout_car_property(request, car_id):
    car = get_object_or_404(CarRental, id=car_id)
    if car.partner_profile is None or car.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': car, 'property_type': 'Car rental'}
    return render(request, 'partners_dashboard/checkout_car_property.html', context)


@partner_required
def checkout_tour_property(request, tour_id):
    tour = get_object_or_404(Tour, id=tour_id)
    if tour.partner_profile is None or tour.partner_profile.user != request.user:
        return HttpResponseForbidden('You do not have permission to access this checkout page.')
    context = {'property': tour, 'property_type': 'Tour'}
    return render(request, 'partners_dashboard/checkout_tour_property.html', context)


@partner_required
@require_POST
def set_property_availability(request, service_type, property_id):
    desired_value = request.POST.get('available', '').lower()
    if desired_value not in {'true', 'false'}:
        return HttpResponseBadRequest('Availability must be true or false.')

    desired_availability = desired_value == 'true'
    property_object = owned_property(request.user, service_type, property_id)
    changed = False
    error_message = ''

    if isinstance(property_object, Flight):
        if property_object.status not in {'scheduled', 'cancelled'}:
            error_message = (
                f'{property_object.get_status_display()} flights cannot be opened or closed.'
            )
        elif desired_availability and property_object.available_seats <= 0:
            error_message = 'Add available seats before reopening this flight.'
        else:
            target_status = 'scheduled' if desired_availability else 'cancelled'
            if property_object.status != target_status:
                property_object.status = target_status
                property_object.save(update_fields=['status', 'updated_at'])
                changed = True
    else:
        if property_object.is_available != desired_availability:
            property_object.is_available = desired_availability
            property_object.save(update_fields=['is_available', 'updated_at'])
            changed = True

    if error_message:
        messages.error(request, error_message)
    elif changed:
        state = 'available' if desired_availability else 'offline'
        messages.success(request, f'{property_object} is now {state}.')
    else:
        messages.info(request, 'Availability was already up to date.')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        if error_message:
            return JsonResponse(
                {'status': 'error', 'message': error_message},
                status=400,
            )
        return JsonResponse(
            {
                'status': 'ok',
                'is_available': desired_availability,
                'property_id': property_object.id,
                'service_type': service_type,
            }
        )

    if request.POST.get('return_to') == 'dashboard':
        return redirect('partners_dashboard:partners_dashboard')
    return redirect('partners_dashboard:manage_properties')


@partner_required
@require_POST
def toggle_availability(request):
    """Compatibility endpoint for the earlier hotel-only dashboard action."""
    hotel_id = request.POST.get('hotel_id')
    if not hotel_id:
        return HttpResponseBadRequest('Missing hotel_id')

    hotel = owned_property(request.user, 'hotel', hotel_id)
    hotel.is_available = not hotel.is_available
    hotel.save(update_fields=['is_available', 'updated_at'])
    return JsonResponse(
        {
            'status': 'ok',
            'is_available': hotel.is_available,
            'is_active': hotel.is_available,
            'hotel_id': hotel.id,
        }
    )


@partner_required
@require_POST
def confirm_reservation(request):
    """Compatibility endpoint for reservation actions from older clients."""
    booking_id = request.POST.get('booking_id')
    action = request.POST.get('action')
    if not booking_id or action not in ('confirm', 'cancel', 'complete'):
        return HttpResponseBadRequest('Invalid params')

    with transaction.atomic():
        booking = get_object_or_404(
            partner_bookings(request.user).select_for_update(),
            id=booking_id,
        )
        changed, message = change_booking_status(booking, action)

    if not changed:
        return JsonResponse(
            {'status': 'error', 'message': message},
            status=409,
        )
    return JsonResponse(
        {
            'status': 'ok',
            'booking_id': booking.id,
            'action': action,
            'status_value': booking.status,
            'message': message,
        }
    )
