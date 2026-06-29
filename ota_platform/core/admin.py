from django.contrib import admin
from .models import Currency, Country, City, SiteSettings, Promotion, Newsletter, ConciergeRequest


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'exchange_rate', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'currency', 'is_active')
    list_filter = ('currency', 'is_active')
    search_fields = ('name', 'code')


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'is_popular', 'is_active')
    list_filter = ('country', 'is_popular', 'is_active')
    search_fields = ('name', 'country__name')


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'default_currency', 'commission_rate','site_description','support_email', 'support_phone',)
    
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'discount_type', 'discount_value', 'valid_from', 'valid_until', 'is_active')
    list_filter = ('discount_type', 'service_type', 'is_active')
    search_fields = ('title', 'code')
    date_hierarchy = 'valid_from'


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email', 'name')


@admin.register(ConciergeRequest)
class ConciergeRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'intent', 'booked', 'booking_reference', 'created_at')
    list_filter = ('booked', 'intent', 'created_at')
    search_fields = ('user__email', 'query', 'booking_reference')
    readonly_fields = ('created_at', 'updated_at', 'processed_at')