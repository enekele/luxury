from django.contrib import admin
from .models import Partner, PartnerCommission, PartnerPayment


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
	list_display = ('company_name', 'user', 'is_active', 'created_at')
	search_fields = ('company_name', 'user__username', 'user__email')
	list_filter = ('is_active',)
	readonly_fields = ('created_at',)


@admin.register(PartnerCommission)
class PartnerCommissionAdmin(admin.ModelAdmin):
	list_display = ('partner', 'amount', 'status', 'order_reference', 'created_at')
	search_fields = ('partner__company_name', 'order_reference')
	list_filter = ('status',)
	readonly_fields = ('created_at',)


@admin.register(PartnerPayment)
class PartnerPaymentAdmin(admin.ModelAdmin):
	list_display = ('partner', 'amount', 'payment_date')
	search_fields = ('partner__company_name',)
	readonly_fields = ()

