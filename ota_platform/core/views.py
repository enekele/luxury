from datetime import datetime
import logging

import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from .models import City, Country, Promotion, Newsletter, SiteSettings, ConciergeRequest
from bookings.models import Booking
from hotels.models import Hotel
from flights.models import Flight
from cars.models import CarRental
from tours.models import Tour
from reviews.models import Review
from api.utils import validate_booking_dates, calculate_booking_total, generate_booking_reference


logger = logging.getLogger(__name__)
AI_HISTORY_LIMIT = 10
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'


def health_check(request):
    """Lightweight endpoint used by the hosting platform."""
    return JsonResponse({'status': 'ok'})


def home(request):
    """Home page view"""
    # Track affiliate referral if present
    affiliate_id = request.GET.get('aff')
    if affiliate_id and request.user.is_authenticated:
        from affiliates.models import AffiliateProfile, AffiliateReferral
        try:
            affiliate = AffiliateProfile.objects.get(affiliate_id=affiliate_id)
            # Create referral if it doesn't exist
            referral, created = AffiliateReferral.objects.get_or_create(
                affiliate=affiliate,
                referred_user=request.user,
                defaults={
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                }
            )
        except AffiliateProfile.DoesNotExist:
            pass
    
    # Get popular destinations
    popular_cities = City.objects.filter(is_popular=True, is_active=True)[:8]
    
    # Get recent reviews
    recent_reviews = Review.objects.filter(is_approved=True).order_by('-created_at')[:6]
    
    # Get active promotions
    active_promotions = Promotion.objects.filter(
        valid_from__lte=timezone.now(),
        valid_until__gte=timezone.now(),
        is_active=True
    )[:3]
    
    # Get featured hotels
    featured_hotels = Hotel.objects.filter(is_featured=True, is_active=True)[:4]
    
    context = {
        'popular_cities': popular_cities,
        'recent_reviews': recent_reviews,
        'active_promotions': active_promotions,
        'featured_hotels': featured_hotels,
    }
    
    return render(request, 'core/home.html', context)


def search(request):
    """Universal search view"""
    query = request.GET.get('q', '')
    service_type = request.GET.get('type', 'all')
    destination = request.GET.get('destination', '')
    
    results = {
        'hotels': [],
        'flights': [],
        'cars': [],
        'tours': [],
    }
    
    if query or destination:
        search_filter = Q()
        if query:
            search_filter |= Q(name__icontains=query) | Q(description__icontains=query)
        if destination:
            search_filter |= Q(city__name__icontains=destination)
        
        if service_type in ['all', 'hotel']:
            results['hotels'] = Hotel.objects.filter(search_filter, is_active=True)[:10]
        
        if service_type in ['all', 'flight']:
            results['flights'] = Flight.objects.filter(
                Q(origin__name__icontains=destination) | 
                Q(destination__name__icontains=destination) if destination else Q(),
                is_active=True
            )[:10]
        
        if service_type in ['all', 'car']:
            results['cars'] = CarRental.objects.filter(search_filter, is_active=True)[:10]
        
        if service_type in ['all', 'tour']:
            results['tours'] = Tour.objects.filter(search_filter, is_active=True)[:10]
    
    context = {
        'query': query,
        'service_type': service_type,
        'destination': destination,
        'results': results,
    }
    
    return render(request, 'core/search.html', context)


def destinations(request):
    """Destinations listing page"""
    countries = Country.objects.filter(is_active=True).prefetch_related('cities')
    
    # Filter by continent if specified
    continent = request.GET.get('continent')
    if continent:
        countries = countries.filter(continent=continent)
    
    paginator = Paginator(countries, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'countries': page_obj,
        'selected_continent': continent,
    }
    
    return render(request, 'core/destinations.html', context)


def destination_detail(request, country_code):
    """Destination detail page"""
    country = get_object_or_404(Country, code=country_code, is_active=True)
    cities = country.cities.filter(is_active=True)
    
    # Get services available in this country
    hotels = Hotel.objects.filter(city__country=country, is_active=True)[:6]
    tours = Tour.objects.filter(destination__country=country, is_active=True)[:6]
    
    context = {
        'country': country,
        'cities': cities,
        'hotels': hotels,
        'tours': tours,
    }
    
    return render(request, 'core/destination_detail.html', context)


def _money_text(value) -> str:
    if value is None:
        return 'price unavailable'
    try:
        return f'{value.currency} {value.amount}'
    except (AttributeError, TypeError):
        return str(value)


def _travel_inventory_context() -> str:
    """Return a small, current inventory snapshot for grounding AI answers."""
    hotels = Hotel.objects.filter(
        is_active=True,
        is_available=True,
    ).select_related('city', 'city__country').order_by('-is_featured', 'name')[:8]
    flights = Flight.objects.filter(
        is_active=True,
        status='scheduled',
        available_seats__gt=0,
        departure_time__gt=timezone.now(),
    ).select_related('airline', 'origin', 'destination').order_by('departure_time')[:8]
    cars = CarRental.objects.filter(
        is_active=True,
        is_available=True,
    ).select_related('car_model', 'car_model__brand', 'city').order_by('price_per_day')[:8]
    tours = Tour.objects.filter(
        is_active=True,
        is_available=True,
    ).select_related('destination', 'category', 'operator').order_by('-is_featured', 'name')[:8]

    lines = ['CURRENT WEBSITE INVENTORY (only recommend items listed here):']
    lines.extend(
        f'Hotel ID {hotel.id}: {hotel.name}; {hotel.city.name}, '
        f'{hotel.city.country.name}; {hotel.star_rating} stars; '
        f'from {_money_text(hotel.price_per_night)} per night.'
        for hotel in hotels
    )
    lines.extend(
        f'Flight ID {flight.id}: {flight.airline.name} {flight.flight_number}; '
        f'{flight.origin.code} to {flight.destination.code}; '
        f'departs {flight.departure_time.isoformat()}; '
        f'economy {_money_text(flight.economy_price)}; '
        f'{flight.available_seats} seats shown available.'
        for flight in flights
    )
    lines.extend(
        f'Car ID {car.id}: {car.car_model}; {car.city.name}; {car.category}; '
        f'{car.passengers} passengers; {_money_text(car.price_per_day)} per day.'
        for car in cars
    )
    lines.extend(
        f'Tour ID {tour.id}: {tour.name}; {tour.destination.name}; '
        f'{tour.category.name}; {_money_text(tour.price_per_person)} per person; '
        f'maximum {tour.max_participants} participants.'
        for tour in tours
    )
    if len(lines) == 1:
        lines.append('No active inventory is currently available.')
    return '\n'.join(lines)


def _get_ai_history(request, mode: str) -> list[dict]:
    history = request.session.get(f'ai_history_{mode}', [])
    return history if isinstance(history, list) else []


def _save_ai_history(request, mode: str, query: str, answer: str) -> None:
    history = _get_ai_history(request, mode)
    history.extend([
        {'role': 'user', 'content': query},
        {'role': 'assistant', 'content': answer},
    ])
    request.session[f'ai_history_{mode}'] = history[-AI_HISTORY_LIMIT:]
    request.session.modified = True


def _extract_response_text(payload: dict) -> str:
    for item in payload.get('output', []):
        if item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if content.get('type') == 'output_text' and content.get('text'):
                return content['text'].strip()
    return ''


def _call_travel_ai(request, query: str, mode: str) -> str:
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    model = getattr(settings, 'OPENAI_MODEL', '')
    if not api_key or not model:
        raise RuntimeError('OPENAI_API_KEY and OPENAI_MODEL must be configured.')

    if mode == 'concierge':
        role = (
            'You are the Luxorwyn concierge. Help customers search the supplied '
            'website inventory, compare suitable options, and collect missing booking '
            'details. Never claim that a booking or payment is complete. Give service '
            'IDs only when they appear in the supplied inventory. Ask the customer to '
            'review the price and proceed to checkout before confirmation.'
        )
    else:
        role = (
            'You are the Luxorwyn travel assistant. Give concise travel-planning help '
            'and recommend only inventory contained in the supplied inventory snapshot. '
            'Do not invent prices, schedules, availability, policies, or service IDs. '
            'Ask a short follow-up question when essential trip details are missing.'
        )

    messages = _get_ai_history(request, mode)
    messages.append({'role': 'user', 'content': query})
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': model,
            'instructions': f'{role}\n\n{_travel_inventory_context()}',
            'input': messages,
            'store': False,
        },
        timeout=30,
    )
    response.raise_for_status()
    answer = _extract_response_text(response.json())
    if not answer:
        raise RuntimeError('The AI response did not contain text.')
    _save_ai_history(request, mode, query, answer)
    return answer


def _extract_concierge_intent(query: str) -> str:
    text = query.lower()
    if any(word in text for word in ['book', 'reserve', 'purchase', 'confirm']):
        return 'booking'
    if any(word in text for word in ['recommend', 'suggest', 'best', 'top', 'where']):
        return 'recommendation'
    if any(word in text for word in ['itinerary', 'plan', 'schedule', 'destination']):
        return 'itinerary'
    if any(word in text for word in ['visa', 'passport', 'entry', 'compliance']):
        return 'compliance'
    return 'general'


def _build_concierge_answer(user, query: str) -> str:
    text = query.lower()
    if user.is_authenticated:
        greeting = f"Hi {user.first_name or user.email}, "
        if getattr(user, 'is_premium', False):
            greeting += 'as a premium member I can book your trip faster and with special attention. '
        else:
            greeting += 'I can help you plan and book your next trip. '
    else:
        greeting = 'I can help you plan your travel and book services for you. '

    if 'hotel' in text or 'stay' in text or 'room' in text:
        return (
            greeting +
            'Tell me where you want to stay, your dates and number of guests, ' 
            'and I can suggest hotels or book a room automatically for you.'
        )
    if 'flight' in text or 'ticket' in text or 'depart' in text or 'arrive' in text:
        return (
            greeting +
            'Tell me your origin, destination, travel dates, and passenger count, ' 
            'and I can help you find the best flight and create the booking.'
        )
    if 'car' in text or 'rental' in text or 'drive' in text:
        return (
            greeting +
            'I can recommend the right car rental and book it for your travel dates. ' 
            'Share the pickup location and duration when you are ready.'
        )
    if 'tour' in text or 'sightseeing' in text or 'excursion' in text:
        return (
            greeting +
            'I can curate local tours and reserve spots based on your destination. ' 
            'Tell me the place, preferred date, and guest count.'
        )
    if 'itinerary' in text or 'plan' in text or 'schedule' in text:
        return (
            greeting +
            'I can build a personalized itinerary for your trip. ' 
            'Share your travel dates, destination, and interests to get started.'
        )
    if 'visa' in text or 'passport' in text or 'entry' in text:
        return (
            greeting +
            'I can help you check visa and passport requirements for your travel plans. ' 
            'Tell me your nationality and destination.'
        )

    if any(word in text for word in ['budget', 'cheap', 'affordable', 'economy']):
        return (
            greeting +
            'I can find budget-friendly options across hotels, flights, cars and tours. ' 
            'Let me know your destination and travel window.'
        )

    return (
        greeting +
        'Ask me about hotels, flights, cars, tours, itinerary planning, or booking actions and I will help.'
    )


def _log_concierge_request(request, query: str, response: str, intent: str, metadata: dict | None = None, booked: bool = False, booking_reference: str = ''):
    return ConciergeRequest.objects.create(
        user=request.user if request.user.is_authenticated else None,
        query=query,
        response=response,
        intent=intent,
        metadata=metadata or {},
        booked=booked,
        booking_reference=booking_reference,
        processed_at=timezone.now()
    )


def concierge(request):
    """AI concierge landing page"""
    return render(request, 'core/concierge.html')


@require_POST
def concierge_chat(request):
    """Handle AI concierge queries."""
    query = request.POST.get('query', '').strip()
    if not query:
        return JsonResponse({
            'success': False,
            'answer': 'Please type a travel request so I can help you.'
        })

    intent = _extract_concierge_intent(query)
    ai_powered = True
    try:
        answer = _call_travel_ai(request, query, mode='concierge')
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        logger.warning('Concierge AI fallback used: %s', exc)
        answer = _build_concierge_answer(request.user, query)
        ai_powered = False
    concierge_request = _log_concierge_request(request, query, answer, intent)

    return JsonResponse({
        'success': True,
        'answer': answer,
        'intent': intent,
        'request_id': concierge_request.id,
        'ai_powered': ai_powered,
    })


@login_required
@require_POST
def concierge_book(request):
    """Create an automated booking via concierge."""
    service_type = request.POST.get('service_type')
    service_id = request.POST.get('service_id')
    booking_date = request.POST.get('booking_date', '').strip()
    check_in = request.POST.get('check_in', '').strip()
    check_out = request.POST.get('check_out', '').strip()
    try:
        guests = int(request.POST.get('guests', '1') or 1)
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Guests must be a whole number.'})
    if guests < 1 or guests > 100:
        return JsonResponse({'success': False, 'message': 'Guests must be between 1 and 100.'})

    default_phone = getattr(request.user, 'phone', '') or ''
    contact_phone = request.POST.get('contact_phone', default_phone).strip()
    special_requests = request.POST.get('special_requests', '').strip()
    query = request.POST.get('query', '').strip()

    if not service_type or not service_id:
        return JsonResponse({'success': False, 'message': 'Please select a service and provide its ID.'})

    service_object = None
    content_type = None
    if service_type == 'hotel':
        service_object = get_object_or_404(Hotel, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Hotel)
        if not check_in or not check_out:
            return JsonResponse({'success': False, 'message': 'Hotel bookings require check-in and check-out dates.'})
        date_errors = validate_booking_dates(check_in, check_out)
        if date_errors:
            return JsonResponse({'success': False, 'message': ' '.join(date_errors)})
        total_keys = (check_in, check_out)
        booking_date_str = check_in
    elif service_type == 'flight':
        service_object = get_object_or_404(Flight, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Flight)
        if not booking_date:
            return JsonResponse({'success': False, 'message': 'Flight bookings require a travel date.'})
        total_keys = (booking_date, booking_date)
        booking_date_str = booking_date
    elif service_type == 'car':
        service_object = get_object_or_404(CarRental, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(CarRental)
        if not check_in or not check_out:
            return JsonResponse({'success': False, 'message': 'Car rentals require pickup and drop-off dates.'})
        date_errors = validate_booking_dates(check_in, check_out)
        if date_errors:
            return JsonResponse({'success': False, 'message': ' '.join(date_errors)})
        total_keys = (check_in, check_out)
        booking_date_str = check_in
    elif service_type == 'tour':
        service_object = get_object_or_404(Tour, id=service_id, is_active=True)
        content_type = ContentType.objects.get_for_model(Tour)
        if not booking_date:
            return JsonResponse({'success': False, 'message': 'Tour bookings require a date.'})
        total_keys = (booking_date, booking_date)
        booking_date_str = booking_date
    else:
        return JsonResponse({'success': False, 'message': 'Invalid service type.'})

    booking_total = calculate_booking_total(
        service_object,
        total_keys[0],
        total_keys[1],
        guests
    )

    if not booking_total:
        return JsonResponse({'success': False, 'message': 'Unable to calculate booking total.'})

    with transaction.atomic():
        booking = Booking.objects.create(
            user=request.user,
            content_type=content_type,
            object_id=service_object.id,
            booking_reference=generate_booking_reference(),
            booking_date=datetime.strptime(booking_date_str, '%Y-%m-%d').date() if booking_date_str else None,
            total_amount=booking_total['total'],
            contact_name=request.user.get_full_name(),
            contact_email=request.user.email,
            contact_phone=contact_phone,
            special_requests=special_requests,
            status='pending'
        )

    metadata = {
        'service_type': service_type,
        'service_id': service_id,
        'check_in': check_in,
        'check_out': check_out,
        'booking_date': booking_date,
        'guests': guests,
    }
    _log_concierge_request(request=request, query=query or 'Automated concierge booking', response='Pending booking created.', intent='booking', metadata=metadata, booked=True, booking_reference=booking.booking_reference)

    return JsonResponse({
        'success': True,
        'message': f'Pending booking created. Complete checkout to confirm it. Reference: {booking.booking_reference}',
        'booking_reference': booking.booking_reference,
        'booking_id': booking.id,
    })


def about(request):
    """About page"""
    return render(request, 'core/about.html')


def contact(request):
    """Contact page"""
    if request.method == 'POST':
        # Handle contact form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Here you would typically send an email or save to database
        messages.success(request, 'Your message has been sent successfully!')
        return redirect('contact')
    
    return render(request, 'core/contact.html')


def newsletter_subscribe(request):
    """Newsletter subscription"""
    if request.method == 'POST':
        email = request.POST.get('email')
        name = request.POST.get('name', '')
        
        if email:
            newsletter, created = Newsletter.objects.get_or_create(
                email=email,
                defaults={'name': name}
            )
            
            if created:
                messages.success(request, 'Successfully subscribed to newsletter!')
            else:
                messages.info(request, 'You are already subscribed to our newsletter.')
        else:
            messages.error(request, 'Please provide a valid email address.')
    
    return redirect('home')


def privacy_policy(request):
    """Privacy policy page"""
    return render(request, 'core/privacy_policy.html')


def terms_of_service(request):
    """Terms of service page"""
    return render(request, 'core/terms_of_service.html')


def ajax_get_cities(request):
    """AJAX endpoint to get cities for a country"""
    country_id = request.GET.get('country_id')
    cities = City.objects.filter(country_id=country_id, is_active=True).values('id', 'name')
    return JsonResponse(list(cities), safe=False)


def ajax_check_promotion(request):
    """AJAX endpoint to check promotion code validity"""
    code = request.GET.get('code')
    service_type = request.GET.get('service_type', 'all')
    
    try:
        promotion = Promotion.objects.get(code=code, is_active=True)
        if promotion.is_valid and (promotion.service_type == 'all' or promotion.service_type == service_type):
            return JsonResponse({
                'valid': True,
                'discount_type': promotion.discount_type,
                'discount_value': float(promotion.discount_value),
                'title': promotion.title,
            })
        else:
            return JsonResponse({'valid': False, 'message': 'Promotion code is not valid or expired.'})
    except Promotion.DoesNotExist:
        return JsonResponse({'valid': False, 'message': 'Invalid promotion code.'})


@require_POST
def travel_assistant(request):
    """AI-powered travel assistant with a deterministic fallback."""
    query = request.POST.get('query', '').strip()
    if not query:
        return JsonResponse({
            'success': False,
            'answer': 'Ask me anything about travel, bookings, destinations, or itinerary planning.'
        })

    try:
        answer = _call_travel_ai(request, query, mode='travel')
        return JsonResponse({
            'success': True,
            'answer': answer,
            'ai_powered': True,
        })
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        logger.warning('Travel assistant AI fallback used: %s', exc)

    text = query.lower()
    answer = 'I can help you find hotels, flights, tours, cars, or give travel tips. What would you like to know?'

    if 'hotel' in text or 'stay' in text or 'room' in text:
        answer = (
            'For hotel bookings, try our Hotels section or search by destination. ' 
            'If you tell me a city or travel date, I can suggest the best match for your stay.'
        )
    elif 'flight' in text or 'ticket' in text or 'departure' in text or 'arrival' in text:
        answer = (
            'I see you are looking for flights. Use the Flights search page to compare routes, ' 
            'or give me your origin and destination and I can recommend the easiest way to book.'
        )
    elif 'car' in text or 'rent' in text or 'rental' in text:
        answer = (
            'Need a car rental? Tell me where you are going and how many passengers you have, ' 
            'and I can help you choose the right car type and pickup options.'
        )
    elif 'tour' in text or 'sightseeing' in text or 'excursion' in text:
        answer = (
            'Looking for tours? I can recommend local experiences, day trips, or guided tours based on your destination.'
        )
    elif 'budget' in text or 'cheap' in text or 'affordable' in text:
        answer = (
            'I can help you find budget-friendly travel options. Search by destination and I will suggest affordable hotels, flights, and tours.'
        )
    elif 'weather' in text or 'climate' in text:
        answer = (
            'Weather can vary by destination. Share the city and travel dates and I can give general advice on what to pack.'
        )
    elif 'visa' in text or 'passport' in text or 'entry' in text:
        answer = (
            'Visa requirements depend on your nationality and destination. For specific guidance, visit the destination page or contact support directly.'
        )
    elif 'recommend' in text or 'suggest' in text or 'best' in text:
        answer = (
            'I can suggest destinations based on your interests: beaches, city breaks, adventures, or cultural trips. Where would you like to go?'
        )

    return JsonResponse({
        'success': True,
        'answer': answer,
        'ai_powered': False,
    })


@require_POST
def visa_copilot(request):
    """Visa Copilot helper endpoint."""
    query = request.POST.get('query', '').strip()
    if not query:
        return JsonResponse({
            'success': False,
            'answer': 'Tell me your destination and nationality so I can help with visa requirements.'
        })

    text = query.lower()
    answer = 'Visa Copilot can help you understand destination entry requirements, passport validity, and application guidance.'

    if 'schengen' in text:
        answer = (
            'Schengen Visa: Most non-EU travelers need a visa for short stays. ' 
            'Ensure your passport is valid for at least 3 months beyond your departure date from the Schengen area.'
        )
    elif 'usa' in text or 'united states' in text or 'america' in text:
        answer = (
            'United States: many visitors can use ESTA for short tourism trips, but business or work travel typically requires a B visa. ' 
            'Check your nationality-specific entry rules before booking.'
        )
    elif 'canada' in text:
        answer = (
            'Canada: many travelers need an eTA or visitor visa. ' 
            'Make sure your passport is valid for the entire stay and apply online before departure.'
        )
    elif 'passport' in text and 'valid' in text:
        answer = (
            'Passport validity is critical. Most countries require at least 6 months validity beyond your return date. ' 
            'If your passport expires soon, renew it before booking travel.'
        )
    elif 'eta' in text or 'electronic travel authorization' in text:
        answer = (
            'Many countries now require an eTA or electronic visa. ' 
            'You should apply online before travel and use the official government portal for your destination.'
        )
    elif 'visa' in text or 'entry' in text:
        answer = (
            'Visa Copilot recommends checking your destination embassy or consulate for the most accurate requirements. ' 
            'If you share the country and your nationality, I can tell you the likely next steps.'
        )

    return JsonResponse({
        'success': True,
        'answer': answer,
    })


@require_POST
def compliance_check(request):
    """Real-time compliance engine for passport, visa and travel restrictions."""
    nationality = request.POST.get('nationality', '').strip()
    destination = request.POST.get('destination', '').strip()
    passport_months = request.POST.get('passport_months', '').strip()
    travel_reason = request.POST.get('travel_reason', '').strip()

    if not nationality or not destination:
        return JsonResponse({
            'success': False,
            'answer': 'Please provide both nationality and destination to run a compliance check.'
        })

    warnings = []
    destination_normalized = destination.lower()
    nationality_normalized = nationality.lower()

    if passport_months.isdigit() and int(passport_months) < 6:
        warnings.append('Your passport should be valid for at least 6 months beyond your return date.')

    schengen_countries = {
        'france', 'germany', 'spain', 'italy', 'netherlands', 'switzerland',
        'austria', 'belgium', 'croatia', 'denmark', 'finland', 'greece',
        'hungary', 'iceland', 'luxembourg', 'malta', 'norway', 'poland',
        'portugal', 'slovakia', 'slovenia', 'sweden', 'estonia', 'latvia',
        'lithuania'
    }

    if destination_normalized in schengen_countries and nationality_normalized not in schengen_countries:
        warnings.append('A Schengen visa may be required for your nationality. Confirm with the local embassy before travel.')

    if destination_normalized in {'usa', 'united states', 'america'} and nationality_normalized not in {'usa', 'canada', 'uk', 'australia', 'new zealand'}:
        warnings.append('A U.S. visa or ESTA is likely required for your destination. Verify the exact category based on your purpose of travel.')

    if destination_normalized == 'canada' and nationality_normalized not in {'canada', 'usa'}:
        warnings.append('Canada usually requires an eTA or visitor visa for non-US travelers.')

    if travel_reason.lower() in {'work', 'business'} and destination_normalized in {'usa', 'united states', 'america'}:
        warnings.append('Business travel to the USA may require a B-1 visa rather than an ESTA.')

    if not warnings:
        answer = (
            'No major compliance issues detected. Please still verify the latest visa and passport rules with official government sources before you travel.'
        )
    else:
        answer = ' '.join(warnings)

    return JsonResponse({
        'success': True,
        'answer': answer,
        'warnings': warnings,
    })
