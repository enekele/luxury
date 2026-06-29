from django.contrib import admin
from .models import PaymentTransaction, WebhookEvent, SubscriptionPackage, UserSubscription


@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'duration_days', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'package', 'start_date', 'expires_at', 'active')
    list_filter = ('active', 'package')
    search_fields = ('user__email', 'package__title')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "email", "amount", "currency", "status", "paid", "created_at")
    list_filter = ("status", "paid", "currency", "created_at")
    search_fields = ("reference", "email", "service_type", "service_id")
    readonly_fields = ("created_at", "updated_at", "gateway_response")
    ordering = ("-created_at",)
    actions = ("action_mark_success", "action_mark_failed")

    def action_mark_success(self, request, queryset):
        updated = 0
        for obj in queryset:
            obj.mark_success(response=None)
            updated += 1
        self.message_user(request, f"Marked {updated} transaction(s) as success.")
    action_mark_success.short_description = "Mark selected transactions as success"

    def action_mark_failed(self, request, queryset):
        updated = 0
        for obj in queryset:
            obj.mark_failed(response=None)
            updated += 1
        self.message_user(request, f"Marked {updated} transaction(s) as failed.")
    action_mark_failed.short_description = "Mark selected transactions as failed"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "received_at", "processed")
    list_filter = ("event_type", "processed", "received_at")
    search_fields = ("event_type", "signature")
    readonly_fields = ("received_at", "processed_at", "payload", "signature")
    ordering = ("-received_at",)
    actions = ("action_mark_processed",)

    def action_mark_processed(self, request, queryset):
        updated = 0
        for obj in queryset:
            obj.mark_processed()
            updated += 1
        self.message_user(request, f"Marked {updated} webhook event(s) as processed.")
    action_mark_processed.short_description = "Mark selected webhook events as processed"
