from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.html import format_html
from hotels.inventory import release_booking_room_inventory
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'user', 'content_object_display', 'room_type', 'booking_date', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'content_type', 'booking_date', 'created_at')
    search_fields = ('booking_reference', 'user__email', 'user__first_name', 'user__last_name', 'contact_name', 'contact_email')
    readonly_fields = ('booking_reference', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('user', 'booking_reference', 'content_type', 'object_id', 'room_type', 'booking_date', 'check_in', 'check_out', 'quantity', 'inventory_reserved')
        }),
        ('Contact Information', {
            'fields': ('contact_name', 'contact_email', 'contact_phone')
        }),
        ('Pricing', {
            'fields': ('total_amount',)
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Additional Information', {
            'fields': ('special_requests',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['confirm_bookings', 'cancel_bookings', 'mark_completed']
    
    def content_object_display(self, obj):
        """Display the booked service with icon"""
        if obj.content_object:
            service_type = obj.content_type.model
            icons = {
                'hotel': '🏨',
                'flight': '✈️',
                'carrental': '🚗',
                'tour': '🗺️'
            }
            icon = icons.get(service_type, '📋')
            return format_html(
                '{} <strong>{}</strong><br><small class="text-muted">{}</small>',
                icon,
                str(obj.content_object),
                service_type.title()
            )
        return '-'
    content_object_display.short_description = 'Service'
    content_object_display.admin_order_field = 'content_type'
    
    def confirm_bookings(self, request, queryset):
        """Bulk confirm bookings"""
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, f'{updated} bookings confirmed successfully.')
    confirm_bookings.short_description = "Confirm selected bookings"
    
    def cancel_bookings(self, request, queryset):
        """Bulk cancel bookings and return any held room inventory."""
        updated = 0
        with transaction.atomic():
            bookings = queryset.select_for_update().filter(
                status__in=['pending', 'confirmed']
            )
            for booking in bookings:
                release_booking_room_inventory(booking)
                booking.status = 'cancelled'
                booking.save(update_fields=['status', 'updated_at'])
                updated += 1
        self.message_user(request, f'{updated} bookings cancelled.')
    cancel_bookings.short_description = "Cancel selected bookings"
    
    def mark_completed(self, request, queryset):
        """Mark bookings as completed"""
        updated = queryset.filter(status='confirmed').update(status='completed')
        self.message_user(request, f'{updated} bookings marked as completed.')
    mark_completed.short_description = "Mark selected bookings as completed"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'user', 'content_type', 'room_type'
        ).prefetch_related('content_object')
