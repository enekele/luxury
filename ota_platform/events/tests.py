from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import (
    EventCategory, EventVenue, Event, TicketCategory,
    EventTicket, EventBooking, EventReview
)
from core.models import Country, City

User = get_user_model()


class EventModelTest(TestCase):
    """Test cases for Event model"""
    
    def setUp(self):
        """Set up test data"""
        self.country = Country.objects.create(name='Nigeria')
        self.city = City.objects.create(name='Lagos', country=self.country)
        self.category = EventCategory.objects.create(
            name='Football',
            description='Football matches'
        )
        self.venue = EventVenue.objects.create(
            name='Lage Stadium',
            city=self.city,
            address='123 Main St',
            capacity=50000
        )
        self.user = User.objects.create_user(
            username='organizer',
            email='organizer@test.com'
        )
        self.event = Event.objects.create(
            category=self.category,
            venue=self.venue,
            organizer=self.user,
            name='Super Eagles vs Morocco',
            description='AFCON Finals Match',
            image='test.jpg',
            start_date=timezone.now() + timedelta(days=30),
            end_date=timezone.now() + timedelta(days=30, hours=3),
            total_tickets=50000
        )
    
    def test_event_creation(self):
        """Test event creation"""
        self.assertEqual(self.event.name, 'Super Eagles vs Morocco')
        self.assertEqual(self.event.venue, self.venue)
        self.assertTrue(self.event.is_upcoming)
        self.assertFalse(self.event.is_sold_out)
    
    def test_event_available_tickets(self):
        """Test available tickets calculation"""
        self.event.tickets_sold = 10000
        self.event.save()
        self.assertEqual(self.event.available_tickets, 40000)
    
    def test_ticket_category_creation(self):
        """Test ticket category creation"""
        category = TicketCategory.objects.create(
            event=self.event,
            name='VIP',
            base_price='100.00',
            quantity=5000
        )
        self.assertEqual(category.available_quantity, 5000)


class EventBookingTest(TestCase):
    """Test cases for Event Booking"""
    
    def setUp(self):
        """Set up test data"""
        self.country = Country.objects.create(name='Nigeria')
        self.city = City.objects.create(name='Lagos', country=self.country)
        self.category = EventCategory.objects.create(name='Music')
        self.venue = EventVenue.objects.create(
            name='Eko Hotel',
            city=self.city,
            address='123 Main St',
            capacity=5000
        )
        self.event = Event.objects.create(
            category=self.category,
            venue=self.venue,
            name='Concert 2026',
            description='Music festival',
            image='test.jpg',
            start_date=timezone.now() + timedelta(days=15),
            end_date=timezone.now() + timedelta(days=15, hours=4),
            total_tickets=5000
        )
        self.ticket_category = TicketCategory.objects.create(
            event=self.event,
            name='Standard',
            base_price='50.00',
            quantity=1000
        )
        self.user = User.objects.create_user(
            username='customer',
            email='customer@test.com'
        )
    
    def test_booking_number_generation(self):
        """Test booking number auto-generation"""
        booking = EventBooking.objects.create(
            event=self.event,
            customer=self.user,
            quantity=2,
            ticket_category=self.ticket_category,
            unit_price=self.ticket_category.base_price,
            first_name='John',
            last_name='Doe',
            email='john@test.com'
        )
        self.assertIsNotNone(booking.booking_number)
        self.assertTrue(booking.booking_number.startswith('EVT'))
