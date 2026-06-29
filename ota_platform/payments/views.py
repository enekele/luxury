# ...existing code...
import json
import logging
from datetime import timedelta
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import PaymentTransaction, SubscriptionPackage, UserSubscription
from .paystak import PaystakClient

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_paystack_client() -> PaystakClient:
    return PaystakClient()


def _render_error(request: HttpRequest, message: str, status: int = 200) -> HttpResponse:
    return render(request, "payments/error.html", {"message": message}, status=status)


def start_payment(request: HttpRequest) -> HttpResponse:
    """
    Initialize a Paystack transaction and redirect the customer to the authorization URL.
    Expects POST with 'email'. If 'package_id' is provided, the subscription package price is used.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    package_id = request.POST.get("package_id")
    email = request.POST.get("email", "").strip() or (request.user.email if request.user.is_authenticated else "")

    if not email:
        return _render_error(request, "Email is required for payment.")

    metadata: dict[str, Any] = {}
    amount: int | None = None

    if package_id:
        package = get_object_or_404(SubscriptionPackage, pk=package_id, is_active=True)
        amount = int(package.price.amount * 100)
        metadata = {
            "type": "subscription",
            "package_id": package.id,
        }
        if request.user.is_authenticated:
            metadata["user_id"] = request.user.id
    else:
        amount_raw = request.POST.get("amount", "").strip()
        try:
            amount = int(amount_raw)
            if amount <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return _render_error(request, "Invalid amount. Use integer smallest currency unit (e.g. kobo).")

    callback = request.build_absolute_uri(reverse("payments:payment_callback"))

    client = _get_paystack_client()
    try:
        resp: Dict[str, Any] = client.initialize_payment(
            email=email,
            amount=amount,
            callback_url=callback,
            metadata=metadata if metadata else None,
        )
    except Exception as exc:
        logger.exception("Error initializing Paystack payment")
        return _render_error(request, f"Payment initialization failed: {exc}")

    if resp.get("status") and isinstance(resp.get("data"), dict):
        auth = resp["data"]
        url = auth.get("authorization_url")
        if url:
            return redirect(url)
        return _render_error(request, "Payment gateway did not return an authorization URL.")
    else:
        message = resp.get("message") or "Unable to initialize payment."
        return _render_error(request, message)


def _save_payment_transaction(data: Dict[str, Any], metadata: dict[str, Any] | None = None) -> PaymentTransaction:
    reference = data.get("reference", "")
    customer_email = ""
    customer = data.get("customer") or {}
    if isinstance(customer, dict):
        customer_email = customer.get("email", "")

    transaction, _ = PaymentTransaction.objects.get_or_create(
        reference=reference,
        defaults={
            "email": customer_email,
            "amount": int(data.get("amount", 0)),
            "currency": data.get("currency", "NGN"),
            "service_type": metadata.get("type") if metadata else data.get("metadata", {}).get("type", ""),
            "service_id": str(metadata.get("package_id") if metadata else data.get("metadata", {}).get("package_id", "")),
            "status": data.get("status", ""),
            "gateway_response": data,
            "paid": data.get("status") == "success",
        },
    )
    if transaction.gateway_response != data or transaction.status != data.get("status"):
        transaction.status = data.get("status", transaction.status)
        transaction.gateway_response = data
        transaction.paid = data.get("status") == "success"
        transaction.save(update_fields=["status", "gateway_response", "paid"])
    return transaction


def payment_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle redirect callback from Paystack. Verifies transaction using the reference query param.
    """
    reference = request.GET.get("reference")
    if not reference:
        return _render_error(request, "Missing transaction reference.")

    client = _get_paystack_client()
    try:
        resp = client.verify_transaction(reference)
    except Exception as exc:
        logger.exception("Error verifying Paystack transaction")
        return _render_error(request, f"Transaction verification failed: {exc}")

    if not resp.get("status") or resp.get("data", {}).get("status") != "success":
        message = resp.get("message") or "Payment verification failed."
        return _render_error(request, message)

    data = resp["data"]
    metadata = data.get("metadata") or {}
    _save_payment_transaction(data, metadata=metadata)

    package = None
    user = None
    if metadata.get("type") == "subscription" and metadata.get("package_id"):
        package = SubscriptionPackage.objects.filter(pk=metadata["package_id"]).first()
        if metadata.get("user_id"):
            user = User.objects.filter(pk=metadata["user_id"]).first()
        elif data.get("customer") and isinstance(data["customer"], dict):
            user = User.objects.filter(email=data["customer"].get("email", "")).first()

        if user and package:
            with transaction.atomic():
                UserSubscription.objects.filter(user=user, active=True).update(active=False)
                start_date = timezone.now()
                expires_at = start_date + timedelta(days=package.duration_days)
                UserSubscription.objects.create(
                    user=user,
                    package=package,
                    start_date=start_date,
                    expires_at=expires_at,
                    active=True,
                )
                user.is_premium = True
                user.premium_expires = expires_at
                user.save(update_fields=["is_premium", "premium_expires"])

    return render(request, "payments/success.html", {"data": data, "package": package})


@csrf_exempt
def webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook endpoint for Paystack events. Verifies signature then processes the event.
    """
    try:
        # Verify signature first
        if not client.verify_webhook_signature(request):
            logger.warning("Invalid Paystack webhook signature")
            return HttpResponseForbidden("Invalid signature")

        payload = json.loads(request.body or b"{}")
        event = payload.get("event")
        data = payload.get("data", {})

        logger.info("Received Paystack webhook: %s", event)

        # Basic handling examples
        if event == "charge.success":
            # Implement fulfillment: mark order paid, send email, etc.
            reference = data.get("reference")
            logger.info("Charge succeeded for reference: %s", reference)
        elif event == "transaction.failed":
            logger.info("Transaction failed: %s", data.get("reference"))
        # Add other event handlers as needed

        return HttpResponse(status=200)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in webhook")
        return HttpResponseBadRequest("Invalid JSON")
    except Exception:
        logger.exception("Error processing webhook")
        return HttpResponse(status=500)
# ...existing code...