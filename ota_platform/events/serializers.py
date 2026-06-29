from rest_framework import serializers
from .models import (
    EventCategory, EventVenue, Event, TicketCategory,
    EventTicket, EventBooking, EventReview
)
from django.contrib.auth import get_user_model

User = get_user_model()


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
        return sum(r.rating for r in reviews) / len(reviews)
    
    def get_review_count(self, obj):
        return obj.reviews.count()


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


class EventTicketSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    category_name = serializers.CharField(source='ticket_category.name', read_only=True)
    
    class Meta:
        model = EventTicket
        fields = [
            'id', 'event', 'event_name', 'ticket_category', 'category_name',
            'ticket_number', 'seat_number', 'buyer', 'status', 'qr_code', 'created_at'
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at']


class EventBookingListSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.name', read_only=True)
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    
    class Meta:
        model = EventBooking
        fields = [
            'id', 'booking_number', 'event', 'event_name', 'customer',
            'customer_username', 'quantity', 'final_price', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'booking_number', 'created_at']


class EventBookingDetailSerializer(serializers.ModelSerializer):
    event = EventListSerializer(read_only=True)
    customer = serializers.StringRelatedField(read_only=True)
    ticket_category = TicketCategorySerializer(read_only=True)
    
    class Meta:
        model = EventBooking
        fields = [
            'id', 'booking_number', 'event', 'customer', 'quantity',
            'ticket_category', 'unit_price', 'total_price', 'discount_amount',
            'final_price', 'status', 'first_name', 'last_name', 'email', 'phone',
            'special_requests', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'booking_number', 'total_price', 'final_price', 'created_at', 'updated_at'
        ]


class EventBookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventBooking
        fields = [
            'event', 'ticket_category', 'quantity', 'first_name', 'last_name',
            'email', 'phone', 'special_requests'
        ]
    
    def validate_quantity(self, value):
        ticket_category = self.initial_data.get('ticket_category')
        if ticket_category:
            try:
                category = TicketCategory.objects.get(id=ticket_category)
                if value < category.min_purchase or value > category.max_purchase:
                    raise serializers.ValidationError(
                        f"Quantity must be between {category.min_purchase} and {category.max_purchase}"
                    )
                if value > category.available_quantity:
                    raise serializers.ValidationError(
                        f"Only {category.available_quantity} tickets available"
                    )
            except TicketCategory.DoesNotExist:
                raise serializers.ValidationError("Invalid ticket category")
        return value


class EventReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    
    class Meta:
        model = EventReview
        fields = [
            'id', 'event', 'reviewer', 'reviewer_name', 'rating', 'title',
            'comment', 'helpful_count', 'created_at'
        ]
        read_only_fields = ['id', 'reviewer', 'helpful_count', 'created_at']


class EventReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventReview
        fields = ['event', 'rating', 'title', 'comment']
    
    def validate(self, data):
        user = self.context['request'].user
        if EventReview.objects.filter(
            event=data['event'],
            reviewer=user
        ).exists():
            raise serializers.ValidationError("You have already reviewed this event")
        return data
