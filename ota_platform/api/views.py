from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta

from .serializers import (
    HotelSerializer, FlightSerializer, CarRentalSerializer, TourSerializer,
    BookingSerializer, ReviewSerializer, UserSerializer, CitySerializer,
    CountrySerializer, PromotionSerializer, FlightSearchSerializer
)
from hotels.inventory import release_booking_room_inventory
from hotels.models import Hotel, HotelAvailability
from flights.models import Flight, FlightSearch
from cars.models import CarRental
from tours.models import Tour
from bookings.models import Booking
from reviews.models import Review
from core.models import City, Country, Promotion
from django.contrib.auth import get_user_model

User = get_user_model()


class HotelViewSet(viewsets.ReadOnlyModelViewSet):
    """Hotel API ViewSet"""
    queryset = Hotel.objects.filter(is_active=True, is_available=True)
    serializer_class = HotelSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'star_rating', 'is_featured', 'is_available']
    search_fields = ['name', 'description', 'city__name', 'city__country__name']
    ordering_fields = ['name', 'price_per_night', 'star_rating', 'created_at']
    ordering = ['-is_featured', 'name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Price range filtering
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(price_per_night__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_per_night__lte=max_price)
        
        # Amenities filtering
        amenities = self.request.query_params.getlist('amenities')
        if amenities:
            for amenity in amenities:
                queryset = queryset.filter(amenities__contains=amenity)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check hotel availability for specific dates"""
        hotel = self.get_object()
        check_in = request.query_params.get('check_in')
        check_out = request.query_params.get('check_out')
        
        if not check_in or not check_out:
            return Response(
                {'error': 'check_in and check_out dates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            availability = HotelAvailability.objects.filter(
                room_type__hotel=hotel,
                room_type__is_active=True,
                date__gte=check_in_date,
                date__lt=check_out_date,
                available_rooms__gt=0
            ).select_related('room_type').order_by('date', 'room_type__name')
            
            serializer = HotelAvailabilitySerializer(availability, many=True)
            return Response(serializer.data)
            
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )


class FlightViewSet(viewsets.ReadOnlyModelViewSet):
    """Flight API ViewSet"""
    queryset = Flight.objects.filter(
        is_active=True,
        status='scheduled',
        available_seats__gt=0,
        departure_time__gt=timezone.now(),
    )
    serializer_class = FlightSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['airline', 'origin', 'destination', 'status', 'is_direct']
    search_fields = ['flight_number', 'airline__name', 'origin__code', 'destination__code']
    ordering_fields = ['departure_time', 'economy_price', 'duration']
    ordering = ['departure_time']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Date filtering
        departure_date = self.request.query_params.get('departure_date')
        if departure_date:
            try:
                date = datetime.strptime(departure_date, '%Y-%m-%d').date()
                queryset = queryset.filter(departure_time__date=date)
            except ValueError:
                pass
        
        # Price range filtering
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(economy_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(economy_price__lte=max_price)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Search flights with specific criteria"""
        serializer = FlightSearchSerializer(data=request.data)
        if serializer.is_valid():
            # Save search for analytics
            if request.user.is_authenticated:
                serializer.save(user=request.user)
            
            # Perform search
            origin_code = request.data.get('origin')
            destination_code = request.data.get('destination')
            departure_date = request.data.get('departure_date')
            
            queryset = self.get_queryset()
            
            if origin_code:
                queryset = queryset.filter(origin__code=origin_code)
            if destination_code:
                queryset = queryset.filter(destination__code=destination_code)
            if departure_date:
                try:
                    date = datetime.strptime(departure_date, '%Y-%m-%d').date()
                    queryset = queryset.filter(departure_time__date=date)
                except ValueError:
                    pass
            
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CarRentalViewSet(viewsets.ReadOnlyModelViewSet):
    """Car Rental API ViewSet"""
    queryset = CarRental.objects.filter(is_active=True, is_available=True)
    serializer_class = CarRentalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city', 'category', 'transmission', 'fuel_type', 'company']
    search_fields = ['car_model__brand__name', 'car_model__name', 'city__name']
    ordering_fields = ['price_per_day', 'car_model__name', 'created_at']
    ordering = ['price_per_day']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Price range filtering
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(price_per_day__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_per_day__lte=max_price)
        
        # Passenger filtering
        min_passengers = self.request.query_params.get('min_passengers')
        if min_passengers:
            queryset = queryset.filter(passengers__gte=min_passengers)
        
        return queryset


class TourViewSet(viewsets.ReadOnlyModelViewSet):
    """Tour API ViewSet"""
    queryset = Tour.objects.filter(is_active=True, is_available=True)
    serializer_class = TourSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'destination', 'difficulty_level', 'is_featured']
    search_fields = ['name', 'description', 'destination__name', 'highlights']
    ordering_fields = ['name', 'price_per_person', 'duration_days', 'created_at']
    ordering = ['-is_featured', 'name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Price range filtering
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        
        if min_price:
            queryset = queryset.filter(price_per_person__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_per_person__lte=max_price)
        
        # Duration filtering
        duration_type = self.request.query_params.get('duration')
        if duration_type == 'half_day':
            queryset = queryset.filter(duration_days=1, duration_hours__lte=6)
        elif duration_type == 'full_day':
            queryset = queryset.filter(duration_days=1, duration_hours__gt=6)
        elif duration_type == 'multi_day':
            queryset = queryset.filter(duration_days__gt=1)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Check tour availability for specific dates"""
        tour = self.get_object()
        date = request.query_params.get('date')
        
        if not date:
            return Response(
                {'error': 'date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            tour_date = datetime.strptime(date, '%Y-%m-%d').date()
            availability = tour.availability.filter(date=tour_date).first()
            
            if availability:
                serializer = TourAvailabilitySerializer(availability)
                return Response(serializer.data)
            else:
                return Response(
                    {'available': False, 'message': 'No availability for this date'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )


class BookingViewSet(viewsets.ModelViewSet):
    """Booking API ViewSet"""
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'content_type']
    ordering_fields = ['created_at', 'booking_date', 'total_amount']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()

        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking.pk)
            if booking.status not in ['pending', 'confirmed']:
                return Response(
                    {'error': 'Booking cannot be cancelled'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            release_booking_room_inventory(booking)
            booking.status = 'cancelled'
            booking.save(update_fields=['status', 'updated_at'])
        
        serializer = self.get_serializer(booking)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    """Review API ViewSet"""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['rating', 'content_type', 'is_approved']
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if self.action == 'list':
            return Review.objects.filter(is_approved=True)
        return Review.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """City API ViewSet"""
    queryset = City.objects.filter(is_active=True)
    serializer_class = CitySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['country', 'is_popular']
    search_fields = ['name', 'country__name']
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular cities"""
        popular_cities = self.queryset.filter(is_popular=True)[:10]
        serializer = self.get_serializer(popular_cities, many=True)
        return Response(serializer.data)


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    """Country API ViewSet"""
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code']


class PromotionViewSet(viewsets.ReadOnlyModelViewSet):
    """Promotion API ViewSet"""
    queryset = Promotion.objects.filter(is_active=True)
    serializer_class = PromotionSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        now = timezone.now()
        return queryset.filter(
            valid_from__lte=now,
            valid_until__gte=now
        )
    
    @action(detail=False, methods=['post'])
    def validate_code(self, request):
        """Validate promotion code"""
        code = request.data.get('code')
        service_type = request.data.get('service_type', 'all')
        
        if not code:
            return Response(
                {'error': 'Promotion code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            promotion = Promotion.objects.get(code=code, is_active=True)
            
            if promotion.is_valid and (promotion.service_type == 'all' or promotion.service_type == service_type):
                return Response({
                    'valid': True,
                    'promotion': PromotionSerializer(promotion).data
                })
            else:
                return Response({
                    'valid': False,
                    'message': 'Promotion code is not valid or expired'
                })
                
        except Promotion.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'Invalid promotion code'
            })


class UserViewSet(viewsets.ModelViewSet):
    """User API ViewSet"""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update current user profile"""
        serializer = self.get_serializer(
            request.user, 
            data=request.data, 
            partial=request.method == 'PATCH'
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SearchViewSet(viewsets.ViewSet):
    """Universal search API"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def list(self, request):
        """Universal search across all services"""
        query = request.query_params.get('q', '')
        service_type = request.query_params.get('type', 'all')
        destination = request.query_params.get('destination', '')
        
        results = {
            'hotels': [],
            'flights': [],
            'cars': [],
            'tours': [],
        }
        
        if query or destination:
            hotel_filter = Q()
            flight_filter = Q()
            car_filter = Q()
            tour_filter = Q()

            if query:
                hotel_filter &= Q(name__icontains=query) | Q(description__icontains=query)
                flight_filter &= (
                    Q(flight_number__icontains=query)
                    | Q(airline__name__icontains=query)
                    | Q(origin__code__icontains=query)
                    | Q(destination__code__icontains=query)
                )
                car_filter &= (
                    Q(car_model__brand__name__icontains=query)
                    | Q(car_model__name__icontains=query)
                    | Q(company__name__icontains=query)
                    | Q(pickup_location__icontains=query)
                )
                tour_filter &= (
                    Q(name__icontains=query)
                    | Q(description__icontains=query)
                    | Q(highlights__icontains=query)
                )
            if destination:
                hotel_filter &= Q(city__name__icontains=destination)
                flight_filter &= (
                    Q(origin__city__name__icontains=destination)
                    | Q(destination__city__name__icontains=destination)
                    | Q(origin__code__icontains=destination)
                    | Q(destination__code__icontains=destination)
                )
                car_filter &= Q(city__name__icontains=destination)
                tour_filter &= Q(destination__name__icontains=destination)
            
            if service_type in ['all', 'hotel']:
                hotels = Hotel.objects.filter(
                    hotel_filter,
                    is_active=True,
                    is_available=True,
                )[:10]
                results['hotels'] = HotelSerializer(hotels, many=True).data
            
            if service_type in ['all', 'flight']:
                flights = Flight.objects.filter(
                    flight_filter,
                    is_active=True,
                    status='scheduled',
                    available_seats__gt=0,
                    departure_time__gt=timezone.now(),
                )[:10]
                results['flights'] = FlightSerializer(flights, many=True).data
            
            if service_type in ['all', 'car']:
                cars = CarRental.objects.filter(
                    car_filter,
                    is_active=True,
                    is_available=True,
                )[:10]
                results['cars'] = CarRentalSerializer(cars, many=True).data
            
            if service_type in ['all', 'tour']:
                tours = Tour.objects.filter(
                    tour_filter,
                    is_active=True,
                    is_available=True,
                )[:10]
                results['tours'] = TourSerializer(tours, many=True).data
        
        return Response(results)


class AnalyticsViewSet(viewsets.ViewSet):
    """Analytics API for admin dashboard"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get dashboard analytics"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Date ranges
        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)
        
        # Basic statistics
        total_users = User.objects.count()
        new_users_30d = User.objects.filter(date_joined__gte=last_30_days).count()
        total_bookings = Booking.objects.count()
        pending_bookings = Booking.objects.filter(status='pending').count()
        
        # Revenue statistics
        from django.db.models import Sum
        total_revenue = Booking.objects.filter(
            status='confirmed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        revenue_30d = Booking.objects.filter(
            status='confirmed',
            created_at__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Service statistics
        from django.db.models import Count
        service_stats = Booking.objects.values('content_type__model').annotate(
            count=Count('id')
        )
        
        return Response({
            'total_users': total_users,
            'new_users_30d': new_users_30d,
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'total_revenue': float(total_revenue) if total_revenue else 0,
            'revenue_30d': float(revenue_30d) if revenue_30d else 0,
            'service_stats': list(service_stats),
        })


# Event ViewSets
class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """Event API ViewSet with filtering and search"""
    from events.models import Event as EventModel
    from api.serializers import EventListSerializer, EventDetailSerializer
    
    queryset = EventModel.objects.filter(is_active=True).order_by('-start_date')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'venue', 'is_featured']
    search_fields = ['name', 'description', 'featured_artists', 'venue__name', 'category__name']
    ordering_fields = ['name', 'start_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            from api.serializers import EventDetailSerializer
            return EventDetailSerializer
        from api.serializers import EventListSerializer
        return EventListSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)
        
        # Filter by availability
        available_only = self.request.query_params.get('available_only', 'false').lower() == 'true'
        if available_only:
            from django.db.models import F
            queryset = queryset.exclude(tickets_sold=F('total_tickets'))
        
        # Filter by upcoming only
        upcoming_only = self.request.query_params.get('upcoming_only', 'false').lower() == 'true'
        if upcoming_only:
            queryset = queryset.filter(start_date__gt=timezone.now())
        
        return queryset.prefetch_related('ticket_categories', 'reviews')
    
    @action(detail=True, methods=['get'])
    def tickets_available(self, request, pk=None):
        """Get available ticket counts for an event"""
        event = self.get_object()
        categories = event.ticket_categories.values(
            'id', 'name', 'available_quantity', 'is_sold_out', 'base_price'
        )
        return Response({
            'event_id': event.id,
            'event_name': event.name,
            'total_available': event.available_tickets,
            'is_sold_out': event.is_sold_out,
            'categories': list(categories)
        })
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get reviews for an event"""
        from api.serializers import EventReviewSerializer
        event = self.get_object()
        reviews = event.reviews.all()
        serializer = EventReviewSerializer(reviews, many=True)
        return Response({
            'event_id': event.id,
            'average_rating': reviews.aggregate(Avg('rating'))['rating__avg'],
            'review_count': reviews.count(),
            'reviews': serializer.data
        })
