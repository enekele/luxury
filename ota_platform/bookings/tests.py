from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from core.models import City, Country
from hotels.models import Hotel, HotelAvailability, RoomType
from users.models import User


class HotelRoomBookingTests(TestCase):
    def setUp(self):
        country = Country.objects.create(name='Kenya', code='KE')
        city = City.objects.create(name='Nairobi', country=country)
        self.hotel = Hotel.objects.create(
            name='Bookable Suites',
            description='A hotel with selectable rooms.',
            city=city,
            address='City Centre',
            price_per_night='150.00',
        )
        self.room_type = RoomType.objects.create(
            hotel=self.hotel,
            name='Deluxe King',
            description='A king room.',
            max_occupancy=2,
            price_per_night='200.00',
            total_rooms=5,
            available_rooms=5,
        )
        self.user = User.objects.create_user(
            email='traveler@example.com',
            username='traveler',
            password='StrongPass123!',
            first_name='Tara',
            last_name='Traveler',
        )
        self.check_in = timezone.localdate() + timezone.timedelta(days=7)
        self.check_out = self.check_in + timezone.timedelta(days=2)

    def booking_payload(self, **overrides):
        payload = {
            'service_type': 'hotel',
            'service_id': self.hotel.id,
            'room_type': self.room_type.id,
            'check_in': self.check_in.isoformat(),
            'check_out': self.check_out.isoformat(),
            'rooms': 2,
            'guests': 3,
            'contact_name': 'Tara Traveler',
            'contact_email': 'traveler@example.com',
            'contact_phone': '+254700000000',
        }
        payload.update(overrides)
        return payload

    def test_hotel_page_has_working_room_selection_controls(self):
        response = self.client.get(
            reverse('hotels:hotel_detail', args=[self.hotel.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="hotelAvailabilityForm"')
        self.assertContains(response, 'name="room_type"')
        self.assertContains(
            response,
            f'data-room-id="{self.room_type.id}"',
        )
        self.assertContains(response, 'Select Room')

    def test_availability_uses_selected_room_and_date_rates(self):
        HotelAvailability.objects.create(
            room_type=self.room_type,
            date=self.check_out - timezone.timedelta(days=1),
            available_rooms=4,
            price_per_night='250.00',
        )

        response = self.client.get(
            reverse('bookings:check_availability'),
            {
                'service_type': 'hotel',
                'service_id': self.hotel.id,
                'room_type': self.room_type.id,
                'check_in': self.check_in.isoformat(),
                'check_out': self.check_out.isoformat(),
                'rooms': 2,
                'guests': 3,
            },
        )

        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['available'])
        self.assertEqual(payload['room_type']['id'], self.room_type.id)
        self.assertEqual(payload['total_price'], '900.00')
        self.assertEqual(payload['currency'], 'USD')
        self.assertEqual(payload['nights'], 2)

    def test_booking_records_room_dates_price_and_reserves_stock(self):
        self.client.login(email=self.user.email, password='StrongPass123!')

        response = self.client.post(
            reverse('bookings:create_booking'),
            self.booking_payload(),
        )

        self.assertRedirects(response, reverse('user_bookings'))
        booking = Booking.objects.get(user=self.user)
        self.assertEqual(booking.room_type, self.room_type)
        self.assertEqual(booking.check_in, self.check_in)
        self.assertEqual(booking.check_out, self.check_out)
        self.assertEqual(booking.quantity, 2)
        self.assertTrue(booking.inventory_reserved)
        self.assertEqual(booking.total_amount.amount, Decimal('800.00'))
        inventory = HotelAvailability.objects.filter(
            room_type=self.room_type,
            date__gte=self.check_in,
            date__lt=self.check_out,
        )
        self.assertEqual(inventory.count(), 2)
        self.assertTrue(all(day.available_rooms == 3 for day in inventory))

        bookings_page = self.client.get(reverse('user_bookings'))
        self.assertContains(bookings_page, self.room_type.name)
        self.assertContains(bookings_page, '2 rooms')

    def test_booking_rejects_sold_out_room(self):
        HotelAvailability.objects.create(
            room_type=self.room_type,
            date=self.check_in,
            available_rooms=0,
            price_per_night='200.00',
        )
        self.client.login(email=self.user.email, password='StrongPass123!')

        response = self.client.post(
            reverse('bookings:create_booking'),
            self.booking_payload(),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertIn('does not have 2 rooms available', response.json()['message'])
        self.assertFalse(Booking.objects.filter(user=self.user).exists())

    def test_booking_rejects_room_from_another_hotel(self):
        other_hotel = Hotel.objects.create(
            name='Other Hotel',
            description='Not the selected hotel.',
            city=self.hotel.city,
            address='Elsewhere',
            price_per_night='100.00',
        )
        other_room = RoomType.objects.create(
            hotel=other_hotel,
            name='Other Room',
            description='Wrong hotel room.',
            max_occupancy=2,
            price_per_night='100.00',
        )
        self.client.login(email=self.user.email, password='StrongPass123!')

        response = self.client.post(
            reverse('bookings:create_booking'),
            self.booking_payload(room_type=other_room.id),
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Booking.objects.filter(user=self.user).exists())

    def test_cancelling_booking_restores_room_stock_once(self):
        self.client.login(email=self.user.email, password='StrongPass123!')
        self.client.post(
            reverse('bookings:create_booking'),
            self.booking_payload(),
        )
        booking = Booking.objects.get(user=self.user)

        response = self.client.post(
            reverse('bookings:cancel_booking', args=[booking.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertFalse(booking.inventory_reserved)
        inventory = HotelAvailability.objects.filter(
            room_type=self.room_type,
            date__gte=self.check_in,
            date__lt=self.check_out,
        )
        self.assertTrue(all(day.available_rooms == 5 for day in inventory))

        second_response = self.client.post(
            reverse('bookings:cancel_booking', args=[booking.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertFalse(second_response.json()['success'])
        inventory = HotelAvailability.objects.filter(
            room_type=self.room_type,
            date__gte=self.check_in,
            date__lt=self.check_out,
        )
        self.assertTrue(all(day.available_rooms == 5 for day in inventory))
