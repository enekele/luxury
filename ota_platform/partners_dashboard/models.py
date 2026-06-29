from django.db import models
from django.conf import settings
from django.utils import timezone


class Partner(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='partner_profile')
	company_name = models.CharField(max_length=255, blank=True)
	website = models.URLField(blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(default=timezone.now)

	def __str__(self):
		return self.company_name or str(self.user)


class PartnerCommission(models.Model):
	STATUS_PENDING = 'pending'
	STATUS_APPROVED = 'approved'
	STATUS_PAID = 'paid'
	STATUS_CHOICES = [
		(STATUS_PENDING, 'Pending'),
		(STATUS_APPROVED, 'Approved'),
		(STATUS_PAID, 'Paid'),
	]

	partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='commissions')
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
	order_reference = models.CharField(max_length=255, blank=True, null=True)
	created_at = models.DateTimeField(default=timezone.now)

	def __str__(self):
		return f"{self.partner} - {self.amount} ({self.status})"


class PartnerPayment(models.Model):
	partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='payments')
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	payment_date = models.DateTimeField(default=timezone.now)
	notes = models.TextField(blank=True)

	def __str__(self):
		return f"{self.partner} - {self.amount} on {self.payment_date.date()}"

