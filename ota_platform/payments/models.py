from django.db import models
from django.utils import timezone
from djmoney.models.fields import MoneyField


class PaymentTransaction(models.Model):
    """
    Record for an attempted/finished payment via Paystack (or other gateways).
    Stores gateway response so you can reconcile / debug later.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    reference = models.CharField(max_length=128, unique=True, db_index=True)
    email = models.EmailField(blank=True)
    amount = models.BigIntegerField(help_text="Amount in smallest currency unit (e.g. kobo/cents)")
    currency = models.CharField(max_length=8, default="NGN")
    service_type = models.CharField(
        max_length=50, blank=True,
        help_text="Optional: service type this payment is for (e.g. 'booking', 'order')"
    )
    service_id = models.CharField(max_length=64, blank=True, help_text="Optional: related service id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    gateway_response = models.JSONField(null=True, blank=True)
    paid = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} ({self.get_status_display()})"

    def mark_success(self, response: dict | None = None) -> None:
        self.status = "success"
        self.paid = True
        if response is not None:
            self.gateway_response = response
        self.save(update_fields=["status", "paid", "gateway_response", "updated_at"])

    def mark_failed(self, response: dict | None = None) -> None:
        self.status = "failed"
        if response is not None:
            self.gateway_response = response
        self.save(update_fields=["status", "gateway_response", "updated_at"])


class SubscriptionPackage(models.Model):
    """Subscription package definition for premium upgrades."""
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription Package'
        verbose_name_plural = 'Subscription Packages'

    def __str__(self):
        return self.title


class UserSubscription(models.Model):
    """Tracks a user's subscription package purchases and expiry."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='subscriptions')
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.PROTECT)
    start_date = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.user.email} - {self.package.title}"

    @property
    def is_active_subscription(self):
        return self.active and timezone.now() < self.expires_at


class WebhookEvent(models.Model):
    """
    Store incoming webhook payloads for audit / retry / debugging.
    Processed flag indicates whether application processed the event.
    """
    event_type = models.CharField(max_length=128, db_index=True)
    payload = models.JSONField()
    signature = models.CharField(max_length=256, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = "Webhook Event"
        verbose_name_plural = "Webhook Events"

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.received_at.isoformat()}"

    def mark_processed(self) -> None:
        self.processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=["processed", "processed_at"])
