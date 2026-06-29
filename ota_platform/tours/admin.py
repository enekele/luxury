from django.contrib import admin
from .models import (
    TourCategory, TourOperator, Tour, TourImage, TourAvailability,
    TourGuide, TourBooking, TourReview
)


@admin.register(TourCategory)
class TourCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TourOperator)
class TourOperatorAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'is_verified', 'is_active', 'created_at')
    list_filter = ('city__country', 'is_verified', 'is_active', 'created_at')
    search_fields = ('name', 'email', 'city__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'logo', 'website')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'city', 'address')
        }),
        ('Verification', {
            'fields': ('is_verified', 'license_number')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class TourImageInline(admin.TabularInline):
    model = TourImage
    extra = 1
    fields = ('image', 'caption', 'is_primary')


class TourAvailabilityInline(admin.TabularInline):
    model = TourAvailability
    extra = 1
    fields = ('date', 'available_spots', 'price_per_person')


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ('name', 'operator', 'destination', 'category', 'duration_display', 'price_per_person', 'difficulty_level', 'is_featured', 'is_active')
    list_filter = ('category', 'difficulty_level', 'destination__country', 'is_featured', 'is_available', 'is_active', 'created_at')
    search_fields = ('name', 'operator__name', 'destination__name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'average_rating', 'total_reviews', 'duration_display')
    inlines = [TourImageInline, TourAvailabilityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('operator', 'category', 'name', 'description', 'highlights')
        }),
        ('Location & Meeting', {
            'fields': ('destination', 'meeting_point', 'meeting_address')
        }),
        ('Duration & Schedule', {
            'fields': ('duration_days', 'duration_hours', 'start_time', 'end_time', 'available_days')
        }),
        ('Pricing & Capacity', {
            'fields': ('price_per_person', 'child_price', 'max_participants', 'min_participants')
        }),
        ('Tour Details', {
            'fields': ('difficulty_level', 'age_restriction', 'fitness_level', 'languages')
        }),
        ('Inclusions', {
            'fields': ('included', 'excluded', 'schedule')
        }),
        ('Policies', {
            'fields': ('cancellation_policy',)
        }),
        ('Media', {
            'fields': ('main_image',)
        }),
        ('Status & Features', {
            'fields': ('is_featured', 'is_available', 'is_active', 'tags')
        }),
        ('Statistics', {
            'fields': ('average_rating', 'total_reviews'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        return obj.duration_display
    duration_display.short_description = 'Duration'


@admin.register(TourImage)
class TourImageAdmin(admin.ModelAdmin):
    list_display = ('tour', 'caption', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('tour__name', 'caption')


@admin.register(TourAvailability)
class TourAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('tour', 'date', 'available_spots', 'price_per_person')
    list_filter = ('date', 'tour__category')
    search_fields = ('tour__name',)
    date_hierarchy = 'date'


@admin.register(TourGuide)
class TourGuideAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience_years', 'is_verified', 'average_rating', 'is_active')
    list_filter = ('is_verified', 'experience_years', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'average_rating')
    
    fieldsets = (
        ('Guide Information', {
            'fields': ('user', 'bio', 'profile_picture')
        }),
        ('Experience', {
            'fields': ('experience_years', 'languages', 'specialties')
        }),
        ('Verification', {
            'fields': ('is_verified', 'license_number')
        }),
        ('Statistics', {
            'fields': ('average_rating',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TourBooking)
class TourBookingAdmin(admin.ModelAdmin):
    list_display = ('tour', 'user', 'booking_date', 'participants', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'booking_date', 'created_at')
    search_fields = ('tour__name', 'user__email', 'contact_name', 'contact_email')
    date_hierarchy = 'booking_date'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('tour', 'user', 'guide', 'booking_date')
        }),
        ('Participants', {
            'fields': ('participants', 'children')
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


@admin.register(TourReview)
class TourReviewAdmin(admin.ModelAdmin):
    list_display = ('tour', 'user', 'overall_rating', 'is_verified', 'created_at')
    list_filter = ('overall_rating', 'is_verified', 'created_at')
    search_fields = ('tour__name', 'user__email', 'title', 'content')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Review Information', {
            'fields': ('tour', 'user', 'booking', 'title', 'content')
        }),
        ('Ratings', {
            'fields': ('overall_rating', 'value_rating', 'guide_rating', 'organization_rating')
        }),
        ('Status', {
            'fields': ('is_verified',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )