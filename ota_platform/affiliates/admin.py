from django.contrib import admin
from .models import (
    AffiliateProfile, AffiliatePromoCode, AffiliateReferral, 
    AffiliateCommission, AffiliatePayment, AffiliateClick, AffiliateResource
)


@admin.register(AffiliateProfile)
class AffiliateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'affiliate_id', 'business_type', 'commission_rate', 'kyc_status', 'total_earnings', 'is_approved', 'is_active')
    list_filter = ('business_type', 'kyc_status', 'is_approved', 'is_suspended', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'company_name', 'affiliate_id')
    readonly_fields = ('affiliate_id', 'total_referrals', 'total_bookings', 'total_earnings', 'pending_earnings', 'paid_earnings', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'affiliate_id')
        }),
        ('Business Information', {
            'fields': ('company_name', 'business_type', 'business_phone', 'business_email', 'website')
        }),
        ('Social Media', {
            'fields': ('social_media_links', 'follower_count')
        }),
        ('Commission', {
            'fields': ('commission_rate',)
        }),
        ('KYC Information', {
            'fields': ('kyc_status', 'kyc_submitted_at', 'kyc_approved_at', 'kyc_rejection_reason')
        }),
        ('Documents', {
            'fields': ('id_document', 'business_license', 'tax_document')
        }),
        ('Bank Information', {
            'fields': ('bank_name', 'account_holder_name', 'account_number', 'routing_number', 'swift_code')
        }),
        ('Statistics', {
            'fields': ('total_referrals', 'total_bookings', 'total_earnings', 'pending_earnings', 'paid_earnings'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_approved', 'is_suspended', 'suspension_reason')
        }),
        ('Agreement', {
            'fields': ('agreement_accepted', 'agreement_accepted_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_affiliates', 'suspend_affiliates', 'approve_kyc']
    
    def approve_affiliates(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} affiliates approved successfully.")
    approve_affiliates.short_description = "Approve selected affiliates"
    
    def suspend_affiliates(self, request, queryset):
        queryset.update(is_suspended=True)
        self.message_user(request, f"{queryset.count()} affiliates suspended.")
    suspend_affiliates.short_description = "Suspend selected affiliates"
    
    def approve_kyc(self, request, queryset):
        from django.utils import timezone
        queryset.update(kyc_status='approved', kyc_approved_at=timezone.now())
        self.message_user(request, f"KYC approved for {queryset.count()} affiliates.")
    approve_kyc.short_description = "Approve KYC for selected affiliates"


@admin.register(AffiliatePromoCode)
class AffiliatePromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'affiliate', 'discount_type', 'discount_value', 'usage_count', 'usage_limit', 'valid_until', 'is_active')
    list_filter = ('discount_type', 'service_type', 'valid_from', 'valid_until', 'is_active')
    search_fields = ('code', 'affiliate__user__email', 'description')
    readonly_fields = ('usage_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('affiliate', 'code', 'description')
        }),
        ('Discount Settings', {
            'fields': ('discount_type', 'discount_value', 'max_discount', 'min_amount')
        }),
        ('Usage Limits', {
            'fields': ('usage_limit', 'usage_count')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Restrictions', {
            'fields': ('service_type',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(admin.ModelAdmin):
    list_display = ('affiliate', 'referred_user', 'converted', 'conversion_date', 'referred_at')
    list_filter = ('converted', 'conversion_date', 'referred_at')
    search_fields = ('affiliate__user__email', 'referred_user__email')
    readonly_fields = ('referred_at',)
    date_hierarchy = 'referred_at'


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = ('affiliate', 'amount', 'status', 'approved_at', 'paid_at', 'created_at')
    list_filter = ('status', 'approved_at', 'paid_at', 'created_at')
    search_fields = ('affiliate__user__email', 'payment_reference')
    readonly_fields = ('created_at', 'processed_at')
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Commission Information', {
            'fields': ('affiliate',)
        }),
        ('Commission Details', {
            'fields': ('amount', 'payment_details')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Payment Information', {
            'fields': ('approved_at', 'paid_at', 'payment_reference')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_commissions', 'mark_as_paid']
    
    def approve_commissions(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='approved', approved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} commissions approved.")
    approve_commissions.short_description = "Approve selected commissions"
    
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='paid', paid_at=timezone.now())
        self.message_user(request, f"{queryset.count()} commissions marked as paid.")
    mark_as_paid.short_description = "Mark selected commissions as paid"


@admin.register(AffiliatePayment)
class AffiliatePaymentAdmin(admin.ModelAdmin):
    list_display = ('affiliate', 'amount', 'payment_method', 'payment_date', 'status', 'payment_reference')
    list_filter = ('payment_method', 'status', 'payment_date', 'created_at')
    search_fields = ('affiliate__user__email', 'payment_reference')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'payment_date'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('affiliate', 'amount', 'payment_method')
        }),
        ('Payment Details', {
            'fields': ('payment_reference', 'payment_date')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AffiliateClick)
class AffiliateClickAdmin(admin.ModelAdmin):
    list_display = ('affiliate', 'clicked_at', 'ip_address', 'converted', 'conversion_value')
    list_filter = ('converted', 'clicked_at')
    search_fields = ('affiliate__user__email', 'ip_address', 'landing_page')
    readonly_fields = ('clicked_at',)
    date_hierarchy = 'clicked_at'


@admin.register(AffiliateResource)
class AffiliateResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'service_type', 'download_count', 'is_active', 'created_at')
    list_filter = ('resource_type', 'service_type', 'is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('download_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Resource Information', {
            'fields': ('title', 'description', 'resource_type')
        }),
        ('Content', {
            'fields': ('content', 'image', 'download_file')
        }),
        ('Targeting', {
            'fields': ('service_type',)
        }),
        ('Statistics', {
            'fields': ('download_count',),
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