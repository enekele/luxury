import django_filters
from django.db.models import Q
from hotels.models import Hotel
from flights.models import Flight
from cars.models import CarRental
from tours.models import Tour
from bookings.models import Booking


class HotelFilter(django_filters.FilterSet):
    """Advanced hotel filtering"""
    min_price = django_filters.NumberFilter(field_name='price_per_night', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price_per_night', lookup_expr='lte')
    amenities = django_filters.CharFilter(method='filter_amenities')
    city_name = django_filters.CharFilter(field_name='city__name', lookup_expr='icontains')
    country = django_filters.CharFilter(field_name='city__country__code')
    
    class Meta:
        model = Hotel
        fields = ['star_rating', 'is_featured', 'is_available']
    
    def filter_amenities(self, queryset, name, value):
        amenities = value.split(',')
        for amenity in amenities:
            queryset = queryset.filter(amenities__contains=amenity.strip())
        return queryset


class FlightFilter(django_filters.FilterSet):
    """Advanced flight filtering"""
    min_price = django_filters.NumberFilter(field_name='economy_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='economy_price', lookup_expr='lte')
    departure_date = django_filters.DateFilter(field_name='departure_time__date')
    origin_city = django_filters.CharFilter(field_name='origin__city__name', lookup_expr='icontains')
    destination_city = django_filters.CharFilter(field_name='destination__city__name', lookup_expr='icontains')
    max_duration = django_filters.NumberFilter(method='filter_max_duration')
    
    class Meta:
        model = Flight
        fields = ['airline', 'is_direct', 'status']
    
    def filter_max_duration(self, queryset, name, value):
        # Filter flights with duration less than specified hours
        max_seconds = value * 3600  # Convert hours to seconds
        return queryset.filter(duration__lte=max_seconds)


class CarRentalFilter(django_filters.FilterSet):
    """Advanced car rental filtering"""
    min_price = django_filters.NumberFilter(field_name='price_per_day', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price_per_day', lookup_expr='lte')
    min_passengers = django_filters.NumberFilter(field_name='passengers', lookup_expr='gte')
    city_name = django_filters.CharFilter(field_name='city__name', lookup_expr='icontains')
    brand = django_filters.CharFilter(field_name='car_model__brand__name', lookup_expr='icontains')
    
    class Meta:
        model = CarRental
        fields = ['category', 'transmission', 'fuel_type', 'air_conditioning', 'gps']


class TourFilter(django_filters.FilterSet):
    """Advanced tour filtering"""
    min_price = django_filters.NumberFilter(field_name='price_per_person', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price_per_person', lookup_expr='lte')
    destination_name = django_filters.CharFilter(field_name='destination__name', lookup_expr='icontains')
    min_duration = django_filters.NumberFilter(field_name='duration_hours', lookup_expr='gte')
    max_duration = django_filters.NumberFilter(field_name='duration_hours', lookup_expr='lte')
    languages = django_filters.CharFilter(method='filter_languages')
    
    class Meta:
        model = Tour
        fields = ['category', 'difficulty_level', 'is_featured']
    
    def filter_languages(self, queryset, name, value):
        languages = value.split(',')
        for language in languages:
            queryset = queryset.filter(languages__contains=language.strip())
        return queryset


class BookingFilter(django_filters.FilterSet):
    """Booking filtering for admin"""
    date_from = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')
    service_type = django_filters.CharFilter(field_name='content_type__model')
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')
    
    class Meta:
        model = Booking
        fields = ['status']