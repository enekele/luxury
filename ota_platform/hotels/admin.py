from django.contrib import admin
from .models import Hotel, HotelImage, RoomType, HotelAvailability, HotelFacility, HotelPartner


class HotelImageInline(admin.TabularInline):
    model = HotelImage
    extra = 1


class RoomTypeInline(admin.TabularInline):
    model = RoomType
    extra = 1


class HotelPartnerInline(admin.StackedInline):
    model = HotelPartner
    can_delete = False


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'star_rating', 'price_per_night', 'is_featured', 'is_active')
    list_filter = ('star_rating', 'city', 'is_featured', 'is_active')
    search_fields = ('name', 'city__name', 'description')
    inlines = [HotelImageInline, RoomTypeInline, HotelPartnerInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'city', 'address', 'star_rating')
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'partner_commission')
        }),
        ('Images', {
            'fields': ('main_image',)
        }),
        ('Contact Information', {
            'fields': ('phone', 'email', 'website')
        }),
        ('Booking Settings', {
            'fields': ('check_in_time', 'check_out_time', 'cancellation_policy')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_featured', 'is_available', 'is_active')
        }),
        ('Amenities', {
            'fields': ('amenities',)
        }),
    )


@admin.register(HotelImage)
class HotelImageAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'caption', 'is_primary')
    list_filter = ('is_primary', 'hotel')
    search_fields = ('hotel__name', 'caption')


@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'name', 'max_occupancy', 'price_per_night', 'total_rooms', 'available_rooms')
    list_filter = ('hotel', 'max_occupancy')
    search_fields = ('hotel__name', 'name')


@admin.register(HotelAvailability)
class HotelAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'hotel', 'date', 'available_rooms', 'price_per_night')
    list_filter = ('room_type__hotel', 'date')
    search_fields = ('room_type__hotel__name', 'room_type__name')
    date_hierarchy = 'date'

    @admin.display(ordering='room_type__hotel__name', description='Hotel')
    def hotel(self, obj):
        return obj.room_type.hotel


@admin.register(HotelFacility)
class HotelFacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'icon')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(HotelPartner)
class HotelPartnerAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'partner_name', 'partner_id', 'commission_rate')
    list_filter = ('partner_name',)
    search_fields = ('hotel__name', 'partner_name', 'partner_id')
