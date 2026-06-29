from django.contrib import admin
from django.utils.html import format_html
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'content_object_display', 'rating', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved', 'content_type', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'title', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Review Information', {
            'fields': ('user', 'content_type', 'object_id')
        }),
        ('Review Content', {
            'fields': ('rating', 'title', 'comment')
        }),
        ('Moderation', {
            'fields': ('is_approved',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews']
    
    def content_object_display(self, obj):
        """Display the reviewed service with icon"""
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
    
    def approve_reviews(self, request, queryset):
        """Bulk approve reviews"""
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews approved successfully.')
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        """Bulk reject reviews"""
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews rejected.')
    reject_reviews.short_description = "Reject selected reviews"