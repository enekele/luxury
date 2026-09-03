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
from django.views.decorators.http import require_POST

from .models import (
    PaymentTransaction,
    SubscriptionPackage,
    UserSubscription,
    WebhookEvent,
)
from .paystak import PaystakClient
from .services import (
    BookingPaymentError,
    complete_booking_payment,
    fail_booking_payment,
    money_to_minor_units,
    normalize_metadata,
)


logger = logging.getLogger(__name__)
User = get_user_model()


def _get_paystack_client() -> PaystakClient:
    return PaystakClient()


def _render_error(
    request: HttpRequest,
    message: str,
    status: int = 400,
    **context,
) -> HttpResponse:
    return render(
        request,
        'payments/error.html',
        {'message': message, **context},
        status=status,
    )


@require_POST
def start_payment(request: HttpRequest) -> HttpResponse:
    """Initialize a server-priced Paystack subscription transaction."""
    package_id = request.POST.get('package_id')
    email = request.POST.get('email', '').strip() or (
        request.user.email if request.user.is_authenticated else ''
    )
    if not email:
        return _render_error(request, 'Email is required for payment.')
    if not package_id:
        return _render_error(request, 'Select a subscription package to continue.')

    package = get_object_or_404(
        SubscriptionPackage,
        pk=package_id,
        is_active=True,
    )
    metadata: dict[str, Any] = {
        'type': 'subscription',
        'package_id': package.id,
    }
    if request.user.is_authenticated:
        metadata['user_id'] = request.user.id

    callback = request.build_absolute_uri(
        reverse('payments:payment_callback')
    )
    try:
        client = _get_paystack_client()
        response: Dict[str, Any] = client.initialize_payment(
            email=email,
            amount=money_to_minor_units(package.price),
            callback_url=callback,
            metadata=metadata,
            currency=str(package.price.currency),
        )
    except Exception:
        logger.exception('Error initializing Paystack subscription payment')
        return _render_error(
            request,
            'Secure checkout is temporarily unavailable. No charge was made.',
            status=502,
        )

    if not isinstance(response, dict):
        return _render_error(
            request,
            'The payment gateway returned an invalid response.',
            status=502,
        )
    response_data = response.get('data')
    if response.get('status') and isinstance(response_data, dict):
        authorization_url = response_data.get('authorization_url')
        if authorization_url:
            return redirect(authorization_url)
        return _render_error(
            request,
            'The payment gateway did not return a checkout URL.',
            status=502,
        )
    return _render_error(
        request,
        response.get('message') or 'Unable to initialize payment.',
        status=502,
    )


def _save_payment_transaction(
    data: Dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> tuple[PaymentTransaction, bool]:
    """Store a non-booking payment and report whether it first became paid."""
    reference = str(data.get('reference') or '')
    if not reference:
        raise ValueError('Missing payment reference.')

    metadata = metadata or normalize_metadata(data.get('metadata'))
    customer = data.get('customer') or {}
    customer_email = (
        str(customer.get('email') or '') if isinstance(customer, dict) else ''
    )
    try:
        amount = int(data.get('amount', 0))
    except (TypeError, ValueError):
        amount = 0
    status = str(data.get('status') or 'pending')
    service_id = (
        metadata.get('booking_id')
        or metadata.get('package_id')
        or metadata.get('service_id')
        or ''
    )

    with transaction.atomic():
        payment, _ = PaymentTransaction.objects.select_for_update().get_or_create(
            reference=reference,
            defaults={
                'email': customer_email,
                'amount': amount,
                'currency': str(data.get('currency') or 'NGN').upper(),
                'service_type': str(metadata.get('type') or ''),
                'service_id': str(service_id),
                'status': 'pending',
                'gateway_response': None,
                'paid': False,
            },
        )
        first_success = status == 'success' and not payment.paid
        payment.email = customer_email or payment.email
        payment.amount = amount or payment.amount
        payment.currency = str(data.get('currency') or payment.currency).upper()
        payment.service_type = str(metadata.get('type') or payment.service_type)
        payment.service_id = str(service_id or payment.service_id)
        payment.status = status
        payment.gateway_response = data
        payment.paid = status == 'success'
        payment.save()
    return payment, first_success


def _subscription_from_payment(
    data: dict[str, Any],
    metadata: dict[str, Any],
    *,
    activate: bool,
) -> SubscriptionPackage | None:
    if metadata.get('type') != 'subscription' or not metadata.get('package_id'):
        return None

    package = SubscriptionPackage.objects.filter(
        pk=metadata['package_id'],
        is_active=True,
    ).first()
    user = None
    if metadata.get('user_id'):
        user = User.objects.filter(pk=metadata['user_id']).first()
    elif isinstance(data.get('customer'), dict):
        user = User.objects.filter(
            email=data['customer'].get('email', '')
        ).first()

    if activate and user and package:
        with transaction.atomic():
            UserSubscription.objects.filter(user=user, active=True).update(
                active=False
            )
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
            user.save(update_fields=['is_premium', 'premium_expires'])
    return package


def _is_booking_payment(reference: str, metadata: dict[str, Any]) -> bool:
    return metadata.get('type') == 'booking' or PaymentTransaction.objects.filter(
        reference=reference,
        booking__isnull=False,
    ).exists()


def payment_callback(request: HttpRequest) -> HttpResponse:
    """Verify the redirect reference with Paystack before fulfilling payment."""
    reference = request.GET.get('reference', '').strip()
    if not reference:
        return _render_error(request, 'Missing transaction reference.')

    try:
        client = _get_paystack_client()
        response = client.verify_transaction(reference)
    except Exception:
        logger.exception('Error verifying Paystack transaction')
        return _render_error(
            request,
            'We could not verify this transaction yet. Please check your '
            'bookings before trying again.',
            status=502,
        )

    if not isinstance(response, dict):
        return _render_error(
            request,
            'The payment gateway returned an invalid verification response.',
            status=502,
        )
    data = response.get('data')
    if (
        not response.get('status')
        or not isinstance(data, dict)
        or data.get('status') != 'success'
    ):
        if isinstance(data, dict) and data.get('status') in {
            'abandoned',
            'failed',
            'reversed',
        }:
            fail_booking_payment(reference, data)
        return _render_error(
            request,
            response.get('message') or 'Payment verification failed.',
        )

    if str(data.get('reference') or '') != reference:
        return _render_error(request, 'The verified payment reference did not match.')

    metadata = normalize_metadata(data.get('metadata'))
    if _is_booking_payment(reference, metadata):
        try:
            result = complete_booking_payment(data)
        except BookingPaymentError as exc:
            logger.warning(
                'Rejected booking payment %s during callback: %s',
                reference,
                exc,
            )
            return _render_error(
                request,
                'The payment was received but could not be matched safely to '
                'this reservation. Please contact support with the payment reference.',
                status=409,
            )
        if not result.secured:
            return _render_error(
                request,
                'Payment was received, but this reservation is no longer active. '
                'Please contact support so the payment can be reviewed.',
                status=409,
                booking=result.booking,
                payment=result.payment,
            )
        return render(
            request,
            'payments/success.html',
            {
                'data': data,
                'booking': result.booking,
                'payment': result.payment,
            },
        )

    payment, first_success = _save_payment_transaction(data, metadata=metadata)
    package = _subscription_from_payment(
        data,
        metadata,
        activate=first_success,
    )
    return render(
        request,
        'payments/success.html',
        {'data': data, 'package': package, 'payment': payment},
    )


@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
    """Verify and process signed Paystack events, including booking payment."""
    try:
        client = _get_paystack_client()
    except Exception:
        logger.exception('Paystack webhook is not configured')
        return HttpResponse(status=503)

    if not client.verify_webhook_signature(request):
        logger.warning('Invalid Paystack webhook signature')
        return HttpResponseForbidden('Invalid signature')

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        logger.exception('Invalid JSON in Paystack webhook')
        return HttpResponseBadRequest('Invalid JSON')
    if not isinstance(payload, dict):
        return HttpResponseBadRequest('Invalid payload')

    event_type = str(payload.get('event') or '')
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    event_record = WebhookEvent.objects.create(
        event_type=event_type or 'unknown',
        payload=payload,
        signature=request.META.get('HTTP_X_PAYSTACK_SIGNATURE', ''),
    )

    try:
        if event_type == 'charge.success':
            reference = str(data.get('reference') or '')
            metadata = normalize_metadata(data.get('metadata'))
            if _is_booking_payment(reference, metadata):
                result = complete_booking_payment(data)
                if not result.secured:
                    logger.error(
                        'Paid booking %s is no longer secured; manual review required.',
                        result.booking.booking_reference,
                    )
            else:
                _, first_success = _save_payment_transaction(
                    data,
                    metadata=metadata,
                )
                _subscription_from_payment(
                    data,
                    metadata,
                    activate=first_success,
                )
        event_record.mark_processed()
    except BookingPaymentError as exc:
        logger.warning('Rejected Paystack webhook payment: %s', exc)
        return HttpResponseBadRequest('Payment validation failed')
    except Exception:
        logger.exception('Error processing Paystack webhook')
        return HttpResponse(status=500)

    return HttpResponse(status=200)
