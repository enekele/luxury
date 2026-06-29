from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q, Avg, Count, F
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from .models import (
    EventCategory, EventVenue, Event, TicketCategory,
    EventTicket, EventBooking, EventReview
)
from .serializers import (
    EventCategorySerializer, EventVenueSerializer, EventDetailSerializer,
    EventListSerializer, TicketCategorySerializer, EventTicketSerializer,
    EventBookingListSerializer, EventBookingDetailSerializer,
    EventBookingCreateSerializer, EventReviewSerializer, EventReviewCreateSerializer
)


class EventCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Event category viewset"""
    queryset = EventCategory.objects.all()
    serializer_class = EventCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    ordering_fields = ['name']


class EventVenueViewSet(viewsets.ReadOnlyModelViewSet):
    """Event venue viewset"""
    queryset = EventVenue.objects.all()
    serializer_class = EventVenueSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['city']
    search_fields = ['name', 'city__name']
    ordering_fields = ['name', 'capacity']


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """Event viewset with filtering and search"""
    queryset = Event.objects.filter(is_active=True).order_by('-start_date')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'venue', 'is_featured']
    search_fields = ['name', 'description', 'featured_artists', 'venue__name', 'category__name']
    ordering_fields = ['name', 'start_date', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EventDetailSerializer
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
        event = self.get_object()
        reviews = event.reviews.all()
        serializer = EventReviewSerializer(reviews, many=True)
        return Response({
            'event_id': event.id,
            'average_rating': reviews.aggregate(Avg('rating'))['rating__avg'],
            'review_count': reviews.count(),
            'reviews': serializer.data
        })


class TicketCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Ticket category viewset"""
    queryset = TicketCategory.objects.all()
    serializer_class = TicketCategorySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['event']
    
    def get_queryset(self):
        return super().get_queryset().prefetch_related('event')


class EventTicketViewSet(viewsets.ReadOnlyModelViewSet):
    """Event ticket viewset - user's purchased tickets"""
    serializer_class = EventTicketSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event', 'status']
    ordering_fields = ['created_at', 'ticket_number']
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only show tickets purchased by the current user"""
        return EventTicket.objects.filter(
            buyer=self.request.user
        ).select_related('event', 'ticket_category')
    
    @action(detail=True, methods=['post'])
    def generate_qr(self, request, pk=None):
        """Generate QR code for a ticket"""
        ticket = self.get_object()
        if ticket.buyer != request.user:
            return Response(
                {'detail': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Here you would implement QR code generation
        # This is a placeholder
        return Response({
            'ticket_number': ticket.ticket_number,
            'qr_code': str(ticket.qr_code.url) if ticket.qr_code else None
        })


class EventBookingViewSet(viewsets.ModelViewSet):
    """Event booking viewset"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event', 'status']
    ordering_fields = ['created_at', 'booking_number']
    
    def get_queryset(self):
        """Only show bookings for the current user"""
        return EventBooking.objects.filter(
            customer=self.request.user
        ).select_related('event', 'ticket_category')
    
    def get_serializer_class(self):
        if self.action in ['create', 'partial_update']:
            return EventBookingCreateSerializer
        if self.action == 'retrieve':
            return EventBookingDetailSerializer
        return EventBookingListSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new event booking"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set customer
        serializer.validated_data['customer'] = request.user
        
        # Get ticket category and set unit price
        ticket_category = serializer.validated_data['ticket_category']
        serializer.validated_data['unit_price'] = ticket_category.base_price
        
        # Save booking
        booking = serializer.save()
        
        # Update ticket category sold quantity
        ticket_category.quantity_sold += booking.quantity
        ticket_category.save(update_fields=['quantity_sold'])
        
        # Update event ticket sold count
        event = booking.event
        event.tickets_sold += booking.quantity
        event.save(update_fields=['tickets_sold'])
        
        # Create individual tickets
        for i in range(booking.quantity):
            EventTicket.objects.create(
                event=event,
                ticket_category=ticket_category,
                buyer=request.user,
                status='sold'
            )
        
        # Return the created booking
        serializer = EventBookingDetailSerializer(booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        if booking.status == 'cancelled':
            return Response(
                {'detail': 'Booking is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if booking.status == 'completed':
            return Response(
                {'detail': 'Cannot cancel completed booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update booking status
        booking.status = 'cancelled'
        booking.save()
        
        # Revert ticket counts
        booking.ticket_category.quantity_sold -= booking.quantity
        booking.ticket_category.save(update_fields=['quantity_sold'])
        
        booking.event.tickets_sold -= booking.quantity
        booking.event.save(update_fields=['tickets_sold'])
        
        # Update ticket statuses
        EventTicket.objects.filter(
            event=booking.event,
            buyer=request.user
        ).update(status='cancelled')
        
        return Response({
            'status': 'success',
            'message': 'Booking cancelled successfully'
        })
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a booking (after payment)"""
        booking = self.get_object()
        
        if booking.status != 'pending':
            return Response(
                {'detail': 'Only pending bookings can be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'confirmed'
        booking.save()
        
        return Response({
            'status': 'success',
            'message': 'Booking confirmed successfully'
        })


class EventReviewViewSet(viewsets.ModelViewSet):
    """Event review viewset"""
    serializer_class = EventReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event', 'rating']
    ordering_fields = ['rating', 'helpful_count', 'created_at']
    ordering = ['-helpful_count', '-created_at']
    
    def get_queryset(self):
        return EventReview.objects.select_related('event', 'reviewer')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EventReviewCreateSerializer
        return EventReviewSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a review"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set reviewer
        serializer.validated_data['reviewer'] = request.user
        
        review = serializer.save()
        return_serializer = EventReviewSerializer(review)
        return Response(return_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, pk=None):
        """Mark a review as helpful"""
        review = self.get_object()
        review.helpful_count += 1
        review.save(update_fields=['helpful_count'])
        
        return Response({
            'helpful_count': review.helpful_count
        })


# Front-end views for events

def event_list(request):
    """Event listing page"""
    events = Event.objects.filter(is_active=True).order_by('start_date')
    category_id = request.GET.get('category')
    search_query = request.GET.get('q')
    upcoming_only = request.GET.get('upcoming_only') == '1'

    if category_id:
        events = events.filter(category_id=category_id)
    if search_query:
        events = events.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(venue__name__icontains=search_query) |
            Q(featured_artists__icontains=search_query)
        )
    if upcoming_only:
        events = events.filter(start_date__gt=timezone.now())

    categories = EventCategory.objects.all()

    return render(request, 'events/event_list.html', {
        'events': events,
        'categories': categories,
        'selected_category': category_id,
        'search_query': search_query,
        'upcoming_only': upcoming_only,
    })


def event_detail(request, event_id):
    """Event detail page"""
    event = get_object_or_404(Event, id=event_id, is_active=True)
    ticket_categories = event.ticket_categories.all()
    return render(request, 'events/event_detail.html', {
        'event': event,
        'ticket_categories': ticket_categories,
    })


@login_required
def event_checkout(request, event_id):
    """Event ticket checkout page"""
    event = get_object_or_404(Event, id=event_id, is_active=True)
    ticket_categories = event.ticket_categories.all()

    if request.method == 'POST':
        ticket_category_id = request.POST.get('ticket_category')
        quantity = int(request.POST.get('quantity', 1))
        first_name = request.POST.get('first_name', request.user.first_name or '')
        last_name = request.POST.get('last_name', request.user.last_name or '')
        email = request.POST.get('email', request.user.email or '')
        phone = request.POST.get('phone', '')

        try:
            category = event.ticket_categories.get(id=ticket_category_id)
        except TicketCategory.DoesNotExist:
            messages.error(request, 'Please select a valid ticket category.')
            return redirect('events:event_detail', event_id=event.id)

        if quantity < category.min_purchase or quantity > category.max_purchase:
            messages.error(request, f'Please select a quantity between {category.min_purchase} and {category.max_purchase}.')
            return redirect('events:event_checkout', event_id=event.id)

        if quantity > category.available_quantity:
            messages.error(request, f'Only {category.available_quantity} tickets are available for {category.name}.')
            return redirect('events:event_checkout', event_id=event.id)

        with transaction.atomic():
            booking = EventBooking.objects.create(
                event=event,
                customer=request.user,
                ticket_category=category,
                quantity=quantity,
                unit_price=category.base_price,
                discount_amount=0,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                status='confirmed'
            )

            category.quantity_sold += quantity
            category.save(update_fields=['quantity_sold'])

            event.tickets_sold += quantity
            event.save(update_fields=['tickets_sold'])

            for _ in range(quantity):
                EventTicket.objects.create(
                    event=event,
                    ticket_category=category,
                    buyer=request.user,
                    status='sold'
                )

        return redirect('events:booking_success', booking_id=booking.id)

    return render(request, 'events/event_checkout.html', {
        'event': event,
        'ticket_categories': ticket_categories,
    })


@login_required
def booking_success(request, booking_id):
    """Event booking success page"""
    booking = get_object_or_404(EventBooking, id=booking_id, customer=request.user)
    return render(request, 'events/booking_success.html', {
        'booking': booking,
    })
