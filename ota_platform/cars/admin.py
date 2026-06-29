from django.contrib import admin
from .models import (
    CarBrand, CarModel, CarRentalCompany, CarRental, CarRentalImage,
    CarRentalAvailability, CarRentalLocation, CarRentalExtra
)


@admin.register(CarBrand)
class CarBrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ('brand', 'name', 'year', 'is_active')
    list_filter = ('brand', 'year', 'is_active')
    search_fields = ('brand__name', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CarRentalCompany)
class CarRentalCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Company Information', {
            'fields': ('name', 'logo', 'website')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class CarRentalImageInline(admin.TabularInline):
    model = CarRentalImage
    extra = 1
    fields = ('image', 'caption', 'is_primary')


class CarRentalAvailabilityInline(admin.TabularInline):
    model = CarRentalAvailability
    extra = 1
    fields = ('date', 'is_available', 'price_per_day')


@admin.register(CarRental)
class CarRentalAdmin(admin.ModelAdmin):
    list_display = ('car_model', 'company', 'city', 'category', 'price_per_day', 'is_available', 'is_active')
    list_filter = ('company', 'category', 'transmission', 'fuel_type', 'city__country', 'is_available', 'is_active')
    search_fields = ('car_model__brand__name', 'car_model__name', 'city__name', 'pickup_location')
    readonly_fields = ('created_at', 'updated_at', 'average_rating', 'total_reviews')
    inlines = [CarRentalImageInline, CarRentalAvailabilityInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('company', 'car_model', 'year', 'color', 'license_plate')
        }),
        ('Location', {
            'fields': ('city', 'pickup_location', 'pickup_address')
        }),
        ('Car Specifications', {
            'fields': ('category', 'passengers', 'bags', 'doors', 'transmission', 'fuel_type')
        }),
        ('Features', {
            'fields': ('air_conditioning', 'gps')
        }),
        ('Pricing', {
            'fields': ('price_per_day', 'price_per_week', 'price_per_month', 'security_deposit')
        }),
        ('Insurance & Requirements', {
            'fields': ('insurance_included', 'insurance_cost', 'minimum_age', 'driving_license_required', 'credit_card_required')
        }),
        ('Mileage', {
            'fields': ('mileage_limit', 'extra_mileage_cost')
        }),
        ('Media', {
            'fields': ('main_image',)
        }),
        ('Availability', {
            'fields': ('is_available',)
        }),
        ('Statistics', {
            'fields': ('average_rating', 'total_reviews'),
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


@admin.register(CarRentalImage)
class CarRentalImageAdmin(admin.ModelAdmin):
    list_display = ('car_rental', 'caption', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('car_rental__car_model__brand__name', 'car_rental__car_model__name', 'caption')


@admin.register(CarRentalAvailability)
class CarRentalAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('car_rental', 'date', 'is_available', 'price_per_day')
    list_filter = ('is_available', 'date')
    search_fields = ('car_rental__car_model__brand__name', 'car_rental__car_model__name')
    date_hierarchy = 'date'


@admin.register(CarRentalLocation)
class CarRentalLocationAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'city', 'location_type', 'is_active')
    list_filter = ('company', 'location_type', 'city__country', 'is_active')
    search_fields = ('name', 'company__name', 'city__name', 'address')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Location Information', {
            'fields': ('company', 'name', 'city', 'address', 'location_type')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email')
        }),
        ('Operating Hours', {
            'fields': ('opening_hours',)
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CarRentalExtra)
class CarRentalExtraAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'price_type', 'is_active')
    list_filter = ('category', 'price_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Extra Information', {
            'fields': ('name', 'description', 'category')
        }),
        ('Pricing', {
            'fields': ('price', 'price_type')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )