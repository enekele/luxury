import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from core.models import City, Country
from hotels.models import Hotel, HotelAvailability, RoomType
from payments.models import PaymentTransaction, WebhookEvent
from users.models import User


class HotelBookingPaymentTests(TestCase):
    def setUp(self):
        country = Country.objects.create(name='Ghana', code='GH')
        city = City.objects.create(name='Accra', country=country)
        self.hotel = Hotel.objects.create(
            name='Secure Stay',
            description='A hotel that requires payment to secure a room.',
            city=city,
            address='1 Beach Road',
            price_per_night='180.00',
        )
        self.room_type = RoomType.objects.create(
            hotel=self.hotel,
            name='Ocean Suite',
            description='Suite with an ocean view.',
            max_occupancy=2,
            price_per_night='200.00',
            total_rooms=5,
            available_rooms=5,
        )
        self.user = User.objects.create_user(
            email='paying.guest@example.com',
            username='paying-guest',
            password='StrongPass123!',
            first_name='Paying',
            last_name='Guest',
        )
        self.check_in = timezone.localdate() + timezone.timedelta(days=10)
        self.check_out = self.check_in + timezone.timedelta(days=2)
        self.client.login(
            email=self.user.email,
            password='StrongPass123!',
        )

    def booking_payload(self):
        return {
            'service_type': 'hotel',
            'service_id': self.hotel.pk,
            'room_type': self.room_type.pk,
            'check_in': self.check_in.isoformat(),
            'check_out': self.check_out.isoformat(),
            'rooms': 1,
            'guests': 2,
            'contact_name': 'Paying Guest',
            'contact_email': self.user.email,
            'contact_phone': '+233200000000',
        }

    def start_checkout(self, gateway_response=None):
        gateway = Mock()

        def successful_initialize(**kwargs):
            return {
                'status': True,
                'message': 'Authorization URL created',
                'data': {
                    'authorization_url': 'https://checkout.paystack.test/session',
                    'reference': kwargs['reference'],
                    'access_code': 'test-access-code',
                },
            }

        gateway.initialize_payment.side_effect = (
            successful_initialize
            if gateway_response is None
            else lambda **kwargs: gateway_response
        )
        with patch('payments.services.PaystakClient', return_value=gateway):
            response = self.client.post(
                reverse('bookings:create_booking'),
                self.booking_payload(),
                HTTP_REFERER=reverse(
                    'hotels:hotel_detail',
                    args=[self.hotel.pk],
                ),
            )
        booking = Booking.objects.get(user=self.user)
        payment = PaymentTransaction.objects.get(booking=booking)
        return response, booking, payment, gateway

    def verified_data(self, payment, **overrides):
        data = {
            'reference': payment.reference,
            'status': 'success',
            'amount': payment.amount,
            'currency': payment.currency,
            'metadata': {
                'type': 'booking',
                'booking_id': payment.booking_id,
                'booking_reference': payment.booking.booking_reference,
                'user_id': payment.booking.user_id,
            },
            'customer': {'email': payment.email},
            'gateway_response': 'Successful',
        }
        data.update(overrides)
        return data

    def test_booking_uses_server_total_and_redirects_to_secure_checkout(self):
        response, booking, payment, gateway = self.start_checkout()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            'https://checkout.paystack.test/session',
        )
        self.assertEqual(payment.amount, 40000)
        self.assertEqual(payment.currency, 'USD')
        self.assertEqual(payment.service_type, 'booking')
        self.assertEqual(payment.service_id, str(booking.pk))
        self.assertFalse(payment.paid)
        self.assertEqual(booking.payment_status, 'pending')
        self.assertEqual(booking.status, 'pending')
        self.assertTrue(booking.inventory_reserved)
        self.assertIsNotNone(booking.expires_at)

        initialize_kwargs = gateway.initialize_payment.call_args.kwargs
        self.assertEqual(initialize_kwargs['amount'], 40000)
        self.assertEqual(initialize_kwargs['currency'], 'USD')
        self.assertEqual(initialize_kwargs['reference'], payment.reference)
        self.assertEqual(
            initialize_kwargs['metadata']['booking_id'],
            booking.pk,
        )

    def test_verified_payment_secures_room_but_waits_for_partner_confirmation(self):
        _, booking, payment, _ = self.start_checkout()
        data = self.verified_data(payment)
        gateway = Mock()
        gateway.verify_transaction.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': data,
        }

        with patch('payments.views._get_paystack_client', return_value=gateway):
            response = self.client.get(
                reverse('payments:payment_callback'),
                {'reference': payment.reference},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment verified — room secured')
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.payment_status, 'paid')
        self.assertEqual(booking.status, 'pending')
        self.assertTrue(booking.inventory_reserved)
        self.assertIsNone(booking.expires_at)
        self.assertTrue(payment.paid)
        self.assertEqual(payment.status, 'success')

    def test_callback_rejects_amount_mismatch_without_marking_booking_paid(self):
        _, booking, payment, _ = self.start_checkout()
        data = self.verified_data(payment, amount=payment.amount - 100)
        gateway = Mock()
        gateway.verify_transaction.return_value = {
            'status': True,
            'data': data,
        }

        with patch('payments.views._get_paystack_client', return_value=gateway):
            response = self.client.get(
                reverse('payments:payment_callback'),
                {'reference': payment.reference},
            )

        self.assertEqual(response.status_code, 409)
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.payment_status, 'pending')
        self.assertFalse(payment.paid)

    def test_gateway_initialization_failure_cancels_hold_and_restores_inventory(self):
        response, booking, payment, _ = self.start_checkout(
            {'status': False, 'message': 'Gateway unavailable'}
        )

        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertEqual(booking.payment_status, 'unpaid')
        self.assertFalse(booking.inventory_reserved)
        self.assertEqual(payment.status, 'failed')
        inventory = HotelAvailability.objects.filter(
            room_type=self.room_type,
            date__gte=self.check_in,
            date__lt=self.check_out,
        )
        self.assertEqual(inventory.count(), 2)
        self.assertTrue(all(day.available_rooms == 5 for day in inventory))

    def test_availability_releases_an_expired_unpaid_hold(self):
        _, booking, _, _ = self.start_checkout()
        booking.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        booking.save(update_fields=['expires_at'])

        response = self.client.get(
            reverse('bookings:check_availability'),
            {
                'service_type': 'hotel',
                'service_id': self.hotel.pk,
                'room_type': self.room_type.pk,
                'check_in': self.check_in.isoformat(),
                'check_out': self.check_out.isoformat(),
                'rooms': 5,
                'guests': 10,
            },
        )

        self.assertTrue(response.json()['available'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertEqual(booking.payment_status, 'unpaid')
        self.assertFalse(booking.inventory_reserved)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_webhook_secret')
    def test_signed_webhook_secures_booking_without_browser_callback(self):
        _, booking, payment, _ = self.start_checkout()
        payload = {
            'event': 'charge.success',
            'data': self.verified_data(payment),
        }
        body = json.dumps(payload, separators=(',', ':')).encode()
        signature = hmac.new(
            b'sk_test_webhook_secret',
            body,
            hashlib.sha512,
        ).hexdigest()

        response = self.client.post(
            reverse('payments:webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.payment_status, 'paid')
        self.assertEqual(booking.status, 'pending')
        self.assertTrue(payment.paid)
        event = WebhookEvent.objects.get()
        self.assertTrue(event.processed)

        gateway = Mock()
        gateway.verify_transaction.return_value = {
            'status': True,
            'message': 'Verification successful',
            'data': payload['data'],
        }
        with patch('payments.views._get_paystack_client', return_value=gateway):
            callback_response = self.client.get(
                reverse('payments:payment_callback'),
                {'reference': payment.reference},
        )

        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(
            PaymentTransaction.objects.filter(booking=booking).count(),
            1,
        )
        inventory = HotelAvailability.objects.filter(
            room_type=self.room_type,
            date__gte=self.check_in,
            date__lt=self.check_out,
        )
        self.assertTrue(all(day.available_rooms == 4 for day in inventory))

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_webhook_secret')
    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            reverse('payments:webhook'),
            data=b'{"event":"charge.success","data":{}}',
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='invalid',
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(WebhookEvent.objects.exists())
