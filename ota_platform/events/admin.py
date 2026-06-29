from django.contrib import admin
from django.utils.html import format_html
from .models import (
    EventCategory, EventVenue, Event, TicketCategory, 
    EventTicket, EventBooking, EventReview
)


@admin.register(EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'colored_icon', 'created_at']
    search_fields = ['name']
    list_filter = ['created_at']
    
    def colored_icon(self, obj):
        return format_html(
            '<span style="color: {}; font-size: 20px;">■</span> {}',
            obj.color,
            obj.icon
        )
    colored_icon.short_description = 'Icon'


@admin.register(EventVenue)
class EventVenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'capacity', 'created_at']
    search_fields = ['name', 'city__name']
    list_filter = ['city', 'created_at']
    readonly_fields = ['created_at', 'updated_at']


class TicketCategoryInline(admin.TabularInline):
    model = TicketCategory
    extra = 1
    fields = ['name', 'base_price', 'quantity', 'quantity_sold', 'min_purchase', 'max_purchase']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'venue', 'start_date', 'tickets_progress', 'is_active', 'is_featured']
    search_fields = ['name', 'venue__name', 'category__name']
    list_filter = ['category', 'venue', 'is_active', 'is_featured', 'start_date']
    readonly_fields = ['tickets_sold', 'created_at', 'updated_at']
    inlines = [TicketCategoryInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'venue', 'organizer', 'name', 'description', 'image')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'doors_open')
        }),
        ('Details', {
            'fields': ('featured_artists', 'rules', 'age_restriction')
        }),
        ('Ticket Information', {
            'fields': ('total_tickets', 'tickets_sold')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def tickets_progress(self, obj):
        percentage = (obj.tickets_sold / obj.total_tickets * 100) if obj.total_tickets > 0 else 0
        color = 'green' if percentage < 70 else 'orange' if percentage < 90 else 'red'
        return format_html(
            '<div style="width: 100px; height: 20px; background-color: #eee; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; height: 100%; background-color: {}; text-align: center; color: white; font-size: 12px;">'
            '{}%</div></div>',
            percentage, color, int(percentage)
        )
    tickets_progress.short_description = 'Ticket Sales'


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'event', 'base_price', 'availability', 'min_purchase', 'max_purchase']
    search_fields = ['name', 'event__name']
    list_filter = ['event', 'created_at']
    readonly_fields = ['quantity_sold', 'created_at', 'updated_at']
    
    def availability(self, obj):
        color = 'green' if obj.available_quantity > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}/{}</span>',
            color,
            obj.available_quantity,
            obj.quantity
        )
    availability.short_description = 'Available'


@admin.register(EventTicket)
class EventTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'event', 'ticket_category', 'seat_number', 'buyer', 'status']
    search_fields = ['ticket_number', 'event__name', 'buyer__username', 'seat_number']
    list_filter = ['status', 'event', 'ticket_category', 'created_at']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['event', 'ticket_category']
        return self.readonly_fields


@admin.register(EventBooking)
class EventBookingAdmin(admin.ModelAdmin):
    list_display = ['booking_number', 'event', 'customer_name', 'quantity', 'final_price', 'status', 'created_at']
    search_fields = ['booking_number', 'event__name', 'customer__username', 'email']
    list_filter = ['status', 'event', 'ticket_category', 'created_at']
    readonly_fields = ['booking_number', 'total_price', 'final_price', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('booking_number', 'event', 'customer', 'status')
        }),
        ('Customer Details', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Ticket Information', {
            'fields': ('ticket_category', 'quantity', 'unit_price')
        }),
        ('Pricing', {
            'fields': ('total_price', 'discount_amount', 'final_price')
        }),
        ('Additional', {
            'fields': ('special_requests',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def customer_name(self, obj):
        if obj.customer:
            return obj.customer.get_full_name() or obj.customer.username
        return f"{obj.first_name} {obj.last_name}"
    customer_name.short_description = 'Customer'


@admin.register(EventReview)
class EventReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'event', 'reviewer', 'rating', 'helpful_count', 'created_at']
    search_fields = ['title', 'comment', 'event__name', 'reviewer__username']
    list_filter = ['rating', 'event', 'created_at']
    readonly_fields = ['created_at', 'updated_at', 'helpful_count']
