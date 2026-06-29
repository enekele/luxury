from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from djmoney.models.fields import MoneyField
from core.models import BaseModel, City
from decimal import Decimal

User = get_user_model()


class EventCategory(BaseModel):
    """Event category model (e.g., Football, Music, Concert, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)  # Bootstrap icon class
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    
    class Meta:
        verbose_name = _('Event Category')
        verbose_name_plural = _('Event Categories')
        ordering = ['name']
    
    def __str__(self):
        return self.name


class EventVenue(BaseModel):
    """Venue/Stadium/Hall model"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='event_venues')
    address = models.TextField()
    capacity = models.IntegerField(validators=[MinValueValidator(1)])
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Contact info
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    
    # Media
    image = models.ImageField(upload_to='venues/', blank=True)
    
    class Meta:
        verbose_name = _('Event Venue')
        verbose_name_plural = _('Event Venues')
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Event(BaseModel):
    """Event model"""
    category = models.ForeignKey(EventCategory, on_delete=models.CASCADE, related_name='events')
    venue = models.ForeignKey(EventVenue, on_delete=models.CASCADE, related_name='events')
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='organized_events')
    
    # Basic info
    name = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='events/')
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    doors_open = models.TimeField(blank=True, null=True)
    
    # Details
    featured_artists = models.CharField(max_length=500, blank=True)  # Comma separated
    rules = models.TextField(blank=True)
    age_restriction = models.IntegerField(null=True, blank=True)  # Minimum age
    
    # Ticket info
    total_tickets = models.IntegerField(validators=[MinValueValidator(1)])
    tickets_sold = models.IntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['-start_date']),
            models.Index(fields=['is_active', '-start_date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.start_date.strftime('%Y-%m-%d')})"
    
    @property
    def available_tickets(self):
        """Returns number of available tickets"""
        return self.total_tickets - self.tickets_sold
    
    @property
    def is_sold_out(self):
        """Check if event is sold out"""
        return self.available_tickets <= 0
    
    @property
    def is_upcoming(self):
        """Check if event is in the future"""
        from django.utils import timezone
        return self.start_date > timezone.now()


class TicketCategory(BaseModel):
    """Ticket category/tier model (VIP, Regular, Economy, etc.)"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_categories')
    name = models.CharField(max_length=100)  # e.g., VIP, Premium, Standard
    description = models.TextField(blank=True)
    
    # Pricing
    base_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    quantity_sold = models.IntegerField(default=0)
    
    # Benefits/Features
    benefits = models.TextField(blank=True)  # Comma separated or detailed description
    
    # Restrictions
    min_purchase = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    max_purchase = models.IntegerField(default=10, validators=[MinValueValidator(1)])
    
    class Meta:
        verbose_name = _('Ticket Category')
        verbose_name_plural = _('Ticket Categories')
        unique_together = [['event', 'name']]
        ordering = ['base_price']
    
    def __str__(self):
        return f"{self.event.name} - {self.name}"
    
    @property
    def available_quantity(self):
        """Returns number of available tickets in this category"""
        return self.quantity - self.quantity_sold
    
    @property
    def is_sold_out(self):
        """Check if ticket category is sold out"""
        return self.available_quantity <= 0


class EventTicket(BaseModel):
    """Individual ticket model"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    ticket_category = models.ForeignKey(TicketCategory, on_delete=models.CASCADE, related_name='tickets')
    
    # Ticket details
    ticket_number = models.CharField(max_length=50, unique=True)
    seat_number = models.CharField(max_length=20, blank=True)
    
    # Buyer
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='purchased_tickets')
    
    # Status
    STATUS_CHOICES = [
        ('available', _('Available')),
        ('sold', _('Sold')),
        ('used', _('Used')),
        ('cancelled', _('Cancelled')),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    
    # QR Code for verification
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    
    class Meta:
        verbose_name = _('Event Ticket')
        verbose_name_plural = _('Event Tickets')
        ordering = ['ticket_number']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['buyer']),
        ]
    
    def __str__(self):
        return f"{self.ticket_number} - {self.event.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate ticket number if not provided
        if not self.ticket_number:
            import uuid
            self.ticket_number = f"{self.event.id}-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)


class EventBooking(BaseModel):
    """Event booking/order model"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='event_bookings')
    
    # Booking details
    booking_number = models.CharField(max_length=50, unique=True)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Pricing
    ticket_category = models.ForeignKey(TicketCategory, on_delete=models.SET_NULL, null=True)
    unit_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    total_price = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    discount_amount = MoneyField(max_digits=10, decimal_places=2, default=0, default_currency='USD')
    final_price = MoneyField(max_digits=12, decimal_places=2, default_currency='USD')
    
    # Status
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Customer details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    
    # Additional info
    special_requests = models.TextField(blank=True)
    
    class Meta:
        verbose_name = _('Event Booking')
        verbose_name_plural = _('Event Bookings')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['customer']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.booking_number} - {self.event.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate booking number if not provided
        if not self.booking_number:
            import uuid
            self.booking_number = f"EVT{timezone.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
        
        # Calculate final price
        self.total_price = self.unit_price * self.quantity
        self.final_price = self.total_price - self.discount_amount
        
        super().save(*args, **kwargs)


class EventReview(BaseModel):
    """Reviews and ratings for events"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_reviews')
    
    rating = models.IntegerField(
        validators=[MinValueValidator(1), ],
        choices=[(i, f'{i}') for i in range(1, 6)]
    )
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Helpful votes
    helpful_count = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Event Review')
        verbose_name_plural = _('Event Reviews')
        unique_together = [['event', 'reviewer']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.event.name} - {self.reviewer.username} ({self.rating}★)"
