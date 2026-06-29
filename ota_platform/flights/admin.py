from django.contrib import admin
from .models import (
    Airline, Airport, Flight, FlightClass, FlightSearch, 
    FlightRoute, FlightDeal
)


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'logo', 'website')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'city', 'is_active')
    list_filter = ('city__country', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'city__name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'city')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'timezone')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class FlightClassInline(admin.TabularInline):
    model = FlightClass
    extra = 1
    fields = ('class_type', 'price', 'available_seats', 'total_seats', 'baggage_allowance', 'meal_service', 'wifi_included')


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ('flight_number', 'airline', 'origin', 'destination', 'departure_time', 'status', 'available_seats', 'is_active')
    list_filter = ('airline', 'status', 'is_direct', 'departure_time', 'is_active')
    search_fields = ('flight_number', 'airline__name', 'origin__code', 'destination__code')
    date_hierarchy = 'departure_time'
    readonly_fields = ('created_at', 'updated_at', 'duration_hours')
    inlines = [FlightClassInline]
    
    fieldsets = (
        ('Flight Information', {
            'fields': ('airline', 'flight_number', 'aircraft_type')
        }),
        ('Route', {
            'fields': ('origin', 'destination', 'is_direct', 'stops')
        }),
        ('Schedule', {
            'fields': ('departure_time', 'arrival_time', 'duration')
        }),
        ('Capacity & Pricing', {
            'fields': ('total_seats', 'available_seats', 'economy_price', 'business_price', 'first_class_price')
        }),
        ('Policies', {
            'fields': ('cancellation_policy', 'baggage_policy')
        }),
        ('Status', {
            'fields': ('status', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def duration_hours(self, obj):
        return f"{obj.duration_hours:.1f}h"
    duration_hours.short_description = 'Duration'


@admin.register(FlightClass)
class FlightClassAdmin(admin.ModelAdmin):
    list_display = ('flight', 'class_type', 'price', 'available_seats', 'total_seats')
    list_filter = ('class_type', 'meal_service', 'wifi_included')
    search_fields = ('flight__flight_number', 'flight__airline__name')


@admin.register(FlightSearch)
class FlightSearchAdmin(admin.ModelAdmin):
    list_display = ('user', 'origin', 'destination', 'departure_date', 'passengers', 'created_at')
    list_filter = ('departure_date', 'class_type', 'created_at')
    search_fields = ('user__email', 'origin__code', 'destination__code')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


@admin.register(FlightRoute)
class FlightRouteAdmin(admin.ModelAdmin):
    list_display = ('origin', 'destination', 'is_popular', 'average_price', 'is_active')
    list_filter = ('is_popular', 'is_active')
    search_fields = ('origin__code', 'destination__code', 'origin__name', 'destination__name')
    
    fieldsets = (
        ('Route Information', {
            'fields': ('origin', 'destination')
        }),
        ('Statistics', {
            'fields': ('average_price', 'average_duration')
        }),
        ('Status', {
            'fields': ('is_popular', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FlightDeal)
class FlightDealAdmin(admin.ModelAdmin):
    list_display = ('title', 'route', 'airline', 'original_price', 'discounted_price', 'discount_percentage', 'valid_until', 'is_active')
    list_filter = ('airline', 'valid_from', 'valid_until', 'is_active')
    search_fields = ('title', 'route__origin__code', 'route__destination__code')
    date_hierarchy = 'valid_from'
    readonly_fields = ('created_at', 'updated_at', 'discount_percentage', 'is_valid')
    
    fieldsets = (
        ('Deal Information', {
            'fields': ('title', 'description', 'route', 'airline')
        }),
        ('Pricing', {
            'fields': ('original_price', 'discounted_price')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Restrictions', {
            'fields': ('min_stay', 'max_stay', 'advance_booking')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Computed Fields', {
            'fields': ('discount_percentage', 'is_valid'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def discount_percentage(self, obj):
        return f"{obj.discount_percentage:.1f}%"
    discount_percentage.short_description = 'Discount %'