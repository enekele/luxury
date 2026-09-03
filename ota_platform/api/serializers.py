from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from hotels.models import Hotel, HotelImage, RoomType, HotelAvailability
from flights.models import Flight, Airline, Airport, FlightClass, FlightSearch
from cars.models import CarRental, CarBrand, CarModel, CarRentalCompany
from tours.models import Tour, TourCategory, TourOperator, TourAvailability
from events.models import Event, EventCategory, EventVenue, TicketCategory, EventReview
from bookings.models import Booking
from reviews.models import Review
from core.models import City, Country, Currency, Promotion
from api.utils import service_is_bookable

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    country = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'phone', 'country', 'city', 'preferred_currency',
            'is_verified', 'is_premium', 'loyalty_points', 'total_bookings'
        ]
        read_only_fields = ['id', 'is_verified', 'is_premium', 'loyalty_points', 'total_bookings']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate']


class CountrySerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'currency', 'timezone']


class CitySerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    
    class Meta:
        model = City
        fields = ['id', 'name', 'country', 'latitude', 'longitude', 'is_popular']


class HotelImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelImage
        fields = ['id', 'image', 'caption', 'is_primary']


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = [
            'id', 'name', 'description', 'max_occupancy', 'price_per_night',
            'size_sqm', 'bed_type', 'amenities', 'total_rooms', 'available_rooms'
        ]


class HotelAvailabilitySerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source='room_type.name', read_only=True)

    class Meta:
        model = HotelAvailability
        fields = [
            'room_type', 'room_type_name', 'date', 'available_rooms',
            'price_per_night',
        ]


class HotelSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    images = HotelImageSerializer(many=True, read_only=True)
    room_types = RoomTypeSerializer(many=True, read_only=True)
    availability = serializers.SerializerMethodField()
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'name', 'description', 'city', 'address', 'star_rating',
            'price_per_night', 'amenities', 'main_image', 'is_featured',
            'is_available', 'phone', 'email', 'website', 'check_in_time',
            'check_out_time', 'latitude', 'longitude', 'images', 'room_types',
            'availability', 'average_rating', 'total_reviews'
        ]

    def get_availability(self, obj):
        records = HotelAvailability.objects.filter(
            room_type__hotel=obj,
            room_type__is_active=True,
            date__gte=timezone.localdate(),
        ).select_related('room_type').order_by('date', 'room_type__name')[:90]
        return HotelAvailabilitySerializer(records, many=True).data


class AirlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airline
        fields = ['id', 'name', 'code', 'logo', 'website']


class AirportSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    
    class Meta:
        model = Airport
        fields = ['id', 'name', 'code', 'city', 'latitude', 'longitude', 'timezone']


class FlightClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightClass
        fields = [
            'id', 'class_type', 'price', 'available_seats', 'total_seats',
            'baggage_allowance', 'meal_service', 'wifi_included', 'seat_selection'
        ]


class FlightSerializer(serializers.ModelSerializer):
    airline = AirlineSerializer(read_only=True)
    origin = AirportSerializer(read_only=True)
    destination = AirportSerializer(read_only=True)
    classes = FlightClassSerializer(many=True, read_only=True)
    duration_hours = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()
    
    class Meta:
        model = Flight
        fields = [
            'id', 'airline', 'flight_number', 'origin', 'destination',
            'departure_time', 'arrival_time', 'duration', 'duration_hours',
            'aircraft_type', 'total_seats', 'available_seats',
            'economy_price', 'business_price', 'first_class_price',
            'status', 'is_direct', 'stops', 'classes', 'is_available'
        ]


class CarBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarBrand
        fields = ['id', 'name', 'logo']


class CarModelSerializer(serializers.ModelSerializer):
    brand = CarBrandSerializer(read_only=True)
    
    class Meta:
        model = CarModel
        fields = ['id', 'brand', 'name', 'year']


class CarRentalCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = CarRentalCompany
        fields = ['id', 'name', 'logo', 'website', 'phone', 'email']


class CarRentalSerializer(serializers.ModelSerializer):
    company = CarRentalCompanySerializer(read_only=True)
    car_model = CarModelSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    
    class Meta:
        model = CarRental
        fields = [
            'id', 'company', 'car_model', 'city', 'pickup_location',
            'pickup_address', 'year', 'color', 'category', 'passengers',
            'bags', 'doors', 'transmission', 'fuel_type', 'air_conditioning',
            'gps', 'price_per_day', 'price_per_week', 'price_per_month',
            'is_available', 'insurance_included', 'minimum_age',
            'security_deposit', 'main_image', 'average_rating', 'total_reviews'
        ]


class TourCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TourCategory
        fields = ['id', 'name', 'description', 'icon']


class TourOperatorSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    
    class Meta:
        model = TourOperator
        fields = [
            'id', 'name', 'description', 'logo', 'website', 'phone',
            'email', 'is_verified', 'city', 'address'
        ]


class TourAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TourAvailability
        fields = ['date', 'available_spots', 'price_per_person']


class TourSerializer(serializers.ModelSerializer):
    operator = TourOperatorSerializer(read_only=True)
    category = TourCategorySerializer(read_only=True)
    destination = CitySerializer(read_only=True)
    availability = TourAvailabilitySerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()
    total_reviews = serializers.ReadOnlyField()
    duration_display = serializers.ReadOnlyField()
    
    class Meta:
        model = Tour
        fields = [
            'id', 'operator', 'category', 'name', 'description', 'highlights',
            'destination', 'meeting_point', 'duration_days', 'duration_hours',
            'duration_display', 'price_per_person', 'child_price',
            'max_participants', 'min_participants', 'difficulty_level',
            'age_restriction', 'languages', 'main_image', 'is_featured',
            'is_available', 'tags', 'availability', 'average_rating', 'total_reviews'
        ]


class BookingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    content_object_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'user', 'content_type', 'object_id', 'content_object_data',
            'booking_reference', 'booking_date', 'room_type', 'check_in',
            'check_out', 'quantity', 'total_amount', 'status',
            'contact_name', 'contact_email', 'contact_phone', 'special_requests',
            'created_at'
        ]
        read_only_fields = [
            'id', 'booking_reference', 'room_type', 'status', 'created_at'
        ]

    def validate(self, attrs):
        content_type = attrs.get(
            'content_type',
            getattr(self.instance, 'content_type', None),
        )
        object_id = attrs.get(
            'object_id',
            getattr(self.instance, 'object_id', None),
        )
        model_class = content_type.model_class() if content_type else None

        if model_class not in {Hotel, Flight, CarRental, Tour}:
            raise serializers.ValidationError(
                {'content_type': 'Choose a supported travel service.'}
            )

        try:
            service_object = model_class.objects.get(id=object_id)
        except model_class.DoesNotExist:
            raise serializers.ValidationError(
                {'object_id': 'The selected travel service does not exist.'}
            )

        if not service_is_bookable(service_object):
            raise serializers.ValidationError(
                {'object_id': 'The selected travel service is not available.'}
            )

        return attrs
    
    def get_content_object_data(self, obj):
        if obj.content_type.model == 'hotel':
            return HotelSerializer(obj.content_object).data
        elif obj.content_type.model == 'flight':
            return FlightSerializer(obj.content_object).data
        elif obj.content_type.model == 'carrental':
            return CarRentalSerializer(obj.content_object).data
        elif obj.content_type.model == 'tour':
            return TourSerializer(obj.content_object).data
        return None


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    content_object_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'content_type', 'object_id', 'content_object_data',
            'rating', 'title', 'comment', 'is_approved', 'created_at'
        ]
        read_only_fields = ['id', 'is_approved', 'created_at']
    
    def get_content_object_data(self, obj):
        if obj.content_type.model == 'hotel':
            return {'name': obj.content_object.name, 'type': 'hotel'}
        elif obj.content_type.model == 'tour':
            return {'name': obj.content_object.name, 'type': 'tour'}
        return None


class PromotionSerializer(serializers.ModelSerializer):
    is_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = Promotion
        fields = [
            'id', 'title', 'description', 'code', 'discount_type',
            'discount_value', 'min_amount', 'max_discount', 'valid_from',
            'valid_until', 'usage_limit', 'used_count', 'service_type',
            'is_valid', 'is_active'
        ]


class FlightSearchSerializer(serializers.ModelSerializer):
    origin = AirportSerializer(read_only=True)
    destination = AirportSerializer(read_only=True)
    
    class Meta:
        model = FlightSearch
        fields = [
            'id', 'origin', 'destination', 'departure_date', 'return_date',
            'passengers', 'class_type', 'created_at'
        ]


# Event Serializers
class EventCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EventCategory
        fields = ['id', 'name', 'description', 'icon', 'color']
        read_only_fields = ['id']


class EventVenueSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    city_country = serializers.CharField(source='city.country.name', read_only=True)
    
    class Meta:
        model = EventVenue
        fields = [
            'id', 'name', 'description', 'city', 'city_name', 'city_country',
            'address', 'capacity', 'latitude', 'longitude', 'phone', 'email',
            'website', 'image', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TicketCategorySerializer(serializers.ModelSerializer):
    available_quantity = serializers.IntegerField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TicketCategory
        fields = [
            'id', 'event', 'name', 'description', 'base_price', 'quantity',
            'quantity_sold', 'available_quantity', 'is_sold_out', 'benefits',
            'min_purchase', 'max_purchase', 'created_at'
        ]
        read_only_fields = ['id', 'quantity_sold', 'created_at']


class EventListSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = serializers.StringRelatedField(read_only=True)
    available_tickets = serializers.IntegerField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'category', 'venue', 'name', 'image', 'start_date', 'end_date',
            'total_tickets', 'tickets_sold', 'available_tickets', 'is_sold_out',
            'is_upcoming', 'is_featured', 'created_at'
        ]
        read_only_fields = ['id', 'tickets_sold', 'created_at']


class EventDetailSerializer(serializers.ModelSerializer):
    category = EventCategorySerializer(read_only=True)
    venue = EventVenueSerializer(read_only=True)
    organizer = serializers.StringRelatedField(read_only=True)
    ticket_categories = TicketCategorySerializer(source='ticket_categories', many=True, read_only=True)
    available_tickets = serializers.IntegerField(read_only=True)
    is_sold_out = serializers.BooleanField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'category', 'venue', 'organizer', 'name', 'description',
            'image', 'start_date', 'end_date', 'doors_open', 'featured_artists',
            'rules', 'age_restriction', 'total_tickets', 'tickets_sold',
            'available_tickets', 'is_sold_out', 'is_upcoming', 'is_active',
            'is_featured', 'ticket_categories', 'average_rating', 'review_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tickets_sold', 'created_at', 'updated_at']
    
    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews:
            return None
        from django.db.models import Avg
        avg = reviews.aggregate(Avg('rating'))['rating__avg']
        return avg
    
    def get_review_count(self, obj):
        return obj.reviews.count()


class EventReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    
    class Meta:
        model = EventReview
        fields = [
            'id', 'event', 'reviewer', 'reviewer_name', 'rating',
            'title', 'comment', 'helpful_count', 'created_at'
        ]
        read_only_fields = ['id', 'reviewer', 'helpful_count', 'created_at']
