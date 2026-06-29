from django.contrib import admin
from .models import AdminActivity, SystemSettings, RevenueReport, PartnerCommission


@admin.register(AdminActivity)
class AdminActivityAdmin(admin.ModelAdmin):
    list_display = ('admin_user', 'action', 'created_at', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('admin_user__email', 'action', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('maintenance_mode', 'auto_confirm_bookings', 'email_notifications_enabled')
    
    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()


@admin.register(RevenueReport)
class RevenueReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'service_type', 'total_bookings', 'total_revenue', 'commission_earned')
    list_filter = ('service_type', 'date')
    date_hierarchy = 'date'


@admin.register(PartnerCommission)
class PartnerCommissionAdmin(admin.ModelAdmin):
    list_display = ('partner_name', 'partner_type', 'commission_rate', 'total_bookings', 'total_commission')
    list_filter = ('partner_type',)
    search_fields = ('partner_name',)

