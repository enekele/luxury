import json
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from hotels.inventory import release_booking_room_inventory

from .models import PaymentTransaction
from .paystak import PaystakClient


logger = logging.getLogger(__name__)


class BookingPaymentError(RuntimeError):
    """Raised when secure checkout cannot be started or verified."""


@dataclass(frozen=True)
class BookingPaymentResult:
    booking: Booking
    payment: PaymentTransaction
    secured: bool


def money_to_minor_units(money) -> int:
    """Convert a two-decimal Money value to the gateway's integer subunit."""
    amount = Decimal(str(money.amount))
    minor_units = int(
        (amount * Decimal('100')).quantize(
            Decimal('1'),
            rounding=ROUND_HALF_UP,
        )
    )
    if minor_units <= 0:
        raise BookingPaymentError('The booking total must be greater than zero.')
    return minor_units


def normalize_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _hold_duration() -> timedelta:
    minutes = max(
        1,
        int(getattr(settings, 'BOOKING_PAYMENT_HOLD_MINUTES', 15)),
    )
    return timedelta(minutes=minutes)


def _booking_metadata(booking: Booking) -> dict[str, Any]:
    return {
        'type': 'booking',
        'booking_id': booking.pk,
        'booking_reference': booking.booking_reference,
        'user_id': booking.user_id,
    }


def _release_failed_booking_hold(booking_id: int) -> None:
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .filter(pk=booking_id)
            .first()
        )
        if not booking or booking.payment_status == 'paid':
            return
        if booking.status == 'pending':
            release_booking_room_inventory(booking)
            booking.status = 'cancelled'
            booking.payment_status = 'unpaid'
            booking.save(
                update_fields=[
                    'status',
                    'payment_status',
                    'updated_at',
                ]
            )


def initialize_booking_payment(
    request,
    booking: Booking,
    *,
    client: PaystakClient | None = None,
) -> str:
    """Create a gateway transaction using only server-calculated booking data."""
    if not request.user.is_authenticated or booking.user_id != request.user.id:
        raise BookingPaymentError('You cannot pay for this booking.')

    payment = None
    response: dict[str, Any] | None = None
    try:
        with transaction.atomic():
            locked_booking = Booking.objects.select_for_update().get(pk=booking.pk)
            if locked_booking.status != 'pending':
                raise BookingPaymentError('This booking is no longer awaiting payment.')
            if locked_booking.payment_status == 'paid':
                raise BookingPaymentError('This booking has already been paid.')
            if not locked_booking.inventory_reserved:
                raise BookingPaymentError('The selected room is no longer being held.')

            locked_booking.payment_status = 'pending'
            locked_booking.expires_at = timezone.now() + _hold_duration()
            locked_booking.save(
                update_fields=['payment_status', 'expires_at', 'updated_at']
            )

            amount = money_to_minor_units(locked_booking.total_amount)
            currency = str(locked_booking.total_amount.currency).upper()
            reference = (
                f'BKG-{locked_booking.booking_reference}-'
                f'{uuid.uuid4().hex[:16].upper()}'
            )
            payment = PaymentTransaction.objects.create(
                reference=reference,
                booking=locked_booking,
                email=locked_booking.contact_email,
                amount=amount,
                currency=currency,
                service_type='booking',
                service_id=str(locked_booking.pk),
                status='pending',
                paid=False,
            )

        callback_url = request.build_absolute_uri(
            reverse('payments:payment_callback')
        )
        gateway = client or PaystakClient()
        response = gateway.initialize_payment(
            email=booking.contact_email,
            amount=payment.amount,
            callback_url=callback_url,
            metadata=_booking_metadata(booking),
            reference=payment.reference,
            currency=payment.currency,
        )
        if not isinstance(response, dict):
            raise BookingPaymentError(
                'The payment gateway returned an invalid response.'
            )
        response_data = response.get('data')
        if not response.get('status') or not isinstance(response_data, dict):
            raise BookingPaymentError(
                response.get('message') or 'The payment gateway could not start checkout.'
            )

        authorization_url = response_data.get('authorization_url')
        gateway_reference = str(response_data.get('reference') or '')
        if not authorization_url or gateway_reference != payment.reference:
            raise BookingPaymentError(
                'The payment gateway returned an invalid checkout session.'
            )

        payment.gateway_response = {'initialize': response}
        payment.save(update_fields=['gateway_response', 'updated_at'])
        return authorization_url
    except Exception as exc:
        if payment is not None:
            payment.status = 'failed'
            payment.paid = False
            payment.gateway_response = (
                {'initialize': response} if response is not None else None
            )
            payment.save(
                update_fields=[
                    'status',
                    'paid',
                    'gateway_response',
                    'updated_at',
                ]
            )
        _release_failed_booking_hold(booking.pk)
        if isinstance(exc, BookingPaymentError):
            raise
        logger.exception(
            'Unexpected error starting payment for booking %s',
            booking.booking_reference,
        )
        raise BookingPaymentError(
            'Secure checkout is temporarily unavailable. No charge was made.'
        ) from exc


def complete_booking_payment(data: dict[str, Any]) -> BookingPaymentResult:
    """Validate a trusted gateway payload and idempotently secure the booking."""
    reference = str(data.get('reference') or '')
    if not reference or data.get('status') != 'success':
        raise BookingPaymentError('The transaction was not successful.')

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .filter(reference=reference, booking__isnull=False)
            .first()
        )
        if not payment or not payment.booking_id:
            raise BookingPaymentError('This payment is not linked to a booking.')

        booking = Booking.objects.select_for_update().get(pk=payment.booking_id)
        try:
            gateway_amount = int(data.get('amount'))
        except (TypeError, ValueError):
            raise BookingPaymentError('The gateway returned an invalid amount.')

        gateway_currency = str(data.get('currency') or '').upper()
        metadata = normalize_metadata(data.get('metadata'))
        customer = data.get('customer') if isinstance(data.get('customer'), dict) else {}
        customer_email = str(customer.get('email') or '').strip().casefold()

        if str(data.get('reference')) != payment.reference:
            raise BookingPaymentError('The transaction reference does not match.')
        if gateway_amount != payment.amount:
            raise BookingPaymentError('The paid amount does not match the booking total.')
        if gateway_currency != payment.currency.upper():
            raise BookingPaymentError('The payment currency does not match the booking.')
        if metadata.get('type') != 'booking':
            raise BookingPaymentError('The transaction purpose does not match this booking.')
        if str(metadata.get('booking_id')) != str(booking.pk):
            raise BookingPaymentError('The transaction booking does not match.')
        if metadata.get('booking_reference') != booking.booking_reference:
            raise BookingPaymentError('The booking reference does not match.')
        if str(metadata.get('user_id')) != str(booking.user_id):
            raise BookingPaymentError('The booking customer does not match.')
        if payment.service_type != 'booking' or payment.service_id != str(booking.pk):
            raise BookingPaymentError('The stored payment link is invalid.')
        if customer_email and payment.email.casefold() != customer_email:
            raise BookingPaymentError('The payer email does not match this booking.')

        payment.status = 'success'
        payment.paid = True
        payment.gateway_response = data
        payment.save(
            update_fields=[
                'status',
                'paid',
                'gateway_response',
                'updated_at',
            ]
        )

        booking.payment_status = 'paid'
        booking.expires_at = None
        booking.save(
            update_fields=['payment_status', 'expires_at', 'updated_at']
        )
        secured = (
            booking.status in {'pending', 'confirmed', 'completed'}
            and booking.inventory_reserved
        )

    return BookingPaymentResult(
        booking=booking,
        payment=payment,
        secured=secured,
    )


def fail_booking_payment(reference: str, data: dict[str, Any]) -> None:
    """Record a terminal gateway failure and release the temporary room hold."""
    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .filter(reference=reference, booking__isnull=False)
            .first()
        )
        if not payment or payment.paid:
            return
        payment.status = 'failed'
        payment.paid = False
        payment.gateway_response = data
        payment.save(
            update_fields=[
                'status',
                'paid',
                'gateway_response',
                'updated_at',
            ]
        )
        booking_id = payment.booking_id

    if booking_id:
        _release_failed_booking_hold(booking_id)


def expire_unpaid_booking_holds(*, room_type_id: int | str | None = None) -> int:
    """Release expired hotel holds opportunistically before quoting inventory."""
    filters: dict[str, Any] = {
        'status': 'pending',
        'payment_status': 'pending',
        'inventory_reserved': True,
        'expires_at__lte': timezone.now(),
        'content_type__model': 'hotel',
    }
    if room_type_id is not None:
        filters['room_type_id'] = room_type_id

    booking_ids = list(
        Booking.objects.filter(**filters).values_list('pk', flat=True)
    )
    expired = 0
    for booking_id in booking_ids:
        with transaction.atomic():
            booking = (
                Booking.objects.select_for_update()
                .filter(pk=booking_id, **filters)
                .first()
            )
            if not booking:
                continue
            release_booking_room_inventory(booking)
            booking.status = 'cancelled'
            booking.payment_status = 'unpaid'
            booking.save(
                update_fields=[
                    'status',
                    'payment_status',
                    'updated_at',
                ]
            )
            expired += 1

    if expired:
        logger.info('Released %s expired hotel booking hold(s).', expired)
    return expired
