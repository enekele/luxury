from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from core.models import Country, City
from flights.models import Airline, Airport, Flight
from hotels.models import Hotel, HotelAvailability, HotelPartner, RoomType
from partners_dashboard.models import Partner
from tours.models import TourCategory, TourOperator, Tour
from cars.models import CarBrand, CarModel, CarRentalCompany, CarRental
from users.models import User


class PartnerPropertyManagementTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Kenya', code='KE', timezone='UTC')
        self.city = City.objects.create(name='Nairobi', country=self.country)
        self.user = User.objects.create_user(
            email='partner@example.com',
            username='partneruser',
            password='StrongPass123!',
            first_name='Jane',
            last_name='Partner',
        )
        self.partner = Partner.objects.create(user=self.user, company_name='Blue Pearl Travel')

        self.hotel = Hotel.objects.create(
            name='Skyline Suites',
            description='Luxury stay',
            city=self.city,
            address='Nairobi CBD',
            star_rating=5,
            price_per_night='150.00',
            is_available=True,
        )
        HotelPartner.objects.create(
            owner=self.user,
            hotel=self.hotel,
            partner_name='Blue Pearl Travel',
            partner_id='BP-1001',
            partner_profile=self.partner,
        )

        self.airline = Airline.objects.create(name='Kenya Airways', code='KQ')
        self.origin = Airport.objects.create(name='Jomo Kenyatta', code='NBO', city=self.city)
        self.destination = Airport.objects.create(name='Mombasa Airport', code='MBA', city=self.city)
        self.flight = Flight.objects.create(
            airline=self.airline,
            flight_number='KQ101',
            origin=self.origin,
            destination=self.destination,
            departure_time=timezone.now() + timezone.timedelta(days=1),
            arrival_time=timezone.now() + timezone.timedelta(days=1, hours=2),
            duration=timezone.timedelta(hours=2),
            total_seats=180,
            available_seats=150,
            economy_price='180.00',
            partner_profile=self.partner,
        )

        self.car_brand = CarBrand.objects.create(name='Toyota')
        self.car_model = CarModel.objects.create(brand=self.car_brand, name='Corolla', year=2024)
        self.car_company = CarRentalCompany.objects.create(name='Blue Pearl Cars')
        self.car = CarRental.objects.create(
            company=self.car_company,
            car_model=self.car_model,
            city=self.city,
            pickup_location='Nairobi Airport',
            pickup_address='Airport Road',
            year=2024,
            category='economy',
            passengers=4,
            bags=2,
            doors=4,
            transmission='automatic',
            fuel_type='gasoline',
            price_per_day='55.00',
            security_deposit='300.00',
            partner_profile=self.partner,
        )

        self.category = TourCategory.objects.create(name='Wildlife')
        self.operator = TourOperator.objects.create(
            name='Wild Rift Tours',
            description='Safari tours',
            email='tours@example.com',
            city=self.city,
            address='Nairobi',
        )
        self.tour = Tour.objects.create(
            operator=self.operator,
            category=self.category,
            name='Nairobi Safari Escape',
            description='A city wildlife adventure',
            destination=self.city,
            meeting_point='Central Nairobi',
            meeting_address='Nairobi CBD',
            duration_days=1,
            duration_hours=8,
            price_per_person='120.00',
            max_participants=12,
            min_participants=2,
            start_time='08:00:00',
            end_time='16:00:00',
            partner_profile=self.partner,
        )

    def create_booking(self, service=None, status='pending', email='guest@example.com'):
        service = service or self.hotel
        customer = User.objects.create_user(
            email=email,
            username=email.split('@')[0],
            password='StrongPass123!',
            first_name='Grace',
            last_name='Guest',
        )
        return Booking.objects.create(
            user=customer,
            content_type=ContentType.objects.get_for_model(service),
            object_id=service.id,
            booking_date=timezone.now().date() + timezone.timedelta(days=7),
            check_in=timezone.now().date() + timezone.timedelta(days=7),
            check_out=timezone.now().date() + timezone.timedelta(days=9),
            total_amount='450.00',
            status=status,
            payment_status='paid',
            contact_name='Grace Guest',
            contact_email=email,
            contact_phone='+2348000000000',
            special_requests='Late arrival requested.',
        )

    def test_partner_can_view_manage_properties_page(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.get(reverse('partners_dashboard:manage_properties'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Skyline Suites')
        self.assertContains(response, 'KQ101')
        self.assertContains(response, 'Nairobi Safari Escape')

    def test_partner_can_create_hotel_property(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse('partners_dashboard:create_hotel_property'),
            {
                'name': 'Palm Grove Hotel',
                'description': 'A new executive stay',
                'country': self.country.id,
                'city': self.city.id,
                'address': 'Upper Hill Nairobi',
                'star_rating': 4,
                'price_per_night_0': Decimal('210.00'),
                'price_per_night_1': 'USD',
                'is_available': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Hotel.objects.filter(name='Palm Grove Hotel').exists())

    def test_partner_can_view_property_checkout_page(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        for url_name, args in [
            ('partners_dashboard:checkout_hotel_property', [self.hotel.id]),
            ('partners_dashboard:checkout_flight_property', [self.flight.id]),
            ('partners_dashboard:checkout_car_property', [self.car.id]),
            ('partners_dashboard:checkout_tour_property', [self.tour.id]),
        ]:
            response = self.client.get(reverse(url_name, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Checkout')

    def test_partner_can_update_hotel_property(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse('partners_dashboard:update_hotel_property', args=[self.hotel.id]),
            {
                'name': 'Skyline Suites Updated',
                'description': 'Updated luxury stay',
                'address': 'Westlands Nairobi',
                'star_rating': 5,
                'price_per_night_0': Decimal('180.00'),
                'price_per_night_1': 'USD',
                'is_available': 'on',
                'is_featured': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.hotel.refresh_from_db()
        self.assertEqual(self.hotel.name, 'Skyline Suites Updated')
        self.assertEqual(self.hotel.address, 'Westlands Nairobi')
        self.assertTrue(self.hotel.is_featured)

    def test_partner_can_update_flight_property(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse('partners_dashboard:update_flight_property', args=[self.flight.id]),
            {
                'flight_number': 'KQ202',
                'status': 'scheduled',
                'available_seats': 180,
                'economy_price_0': Decimal('220.00'),
                'economy_price_1': 'USD',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.flight_number, 'KQ202')

    def test_partner_can_update_car_property(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse('partners_dashboard:update_car_property', args=[self.car.id]),
            {
                'pickup_location': 'Westlands Nairobi',
                'price_per_day_0': Decimal('75.00'),
                'price_per_day_1': 'USD',
                'is_available': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.pickup_location, 'Westlands Nairobi')
        self.assertTrue(self.car.is_available)

    def test_partner_can_update_tour_property(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse('partners_dashboard:update_tour_property', args=[self.tour.id]),
            {
                'name': 'Nairobi Safari Escape Deluxe',
                'description': 'A premium wildlife adventure',
                'meeting_point': 'Westlands',
                'price_per_person_0': Decimal('180.00'),
                'price_per_person_1': 'USD',
                'is_available': 'on',
            }
        )
        self.assertEqual(response.status_code, 302)
        self.tour.refresh_from_db()
        self.assertEqual(self.tour.name, 'Nairobi Safari Escape Deluxe')
        self.assertTrue(self.tour.is_available)

    def test_partner_can_add_and_edit_room_category(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        rooms_url = reverse(
            'partners_dashboard:manage_hotel_rooms',
            args=[self.hotel.id],
        )

        create_response = self.client.post(
            rooms_url,
            {
                'action': 'save_room_type',
                'room-name': 'Deluxe King',
                'room-description': 'Large room with a city view.',
                'room-price_amount': '240.00',
                'room-currency': 'USD',
                'room-max_occupancy': 3,
                'room-total_rooms': 12,
                'room-available_rooms': 8,
                'room-size_sqm': 42,
                'room-bed_type': 'King bed',
                'room-amenities': 'Wi-Fi\nBreakfast, Balcony',
                'room-is_active': 'on',
            },
        )

        self.assertRedirects(create_response, rooms_url)
        room_type = RoomType.objects.get(hotel=self.hotel, name='Deluxe King')
        self.assertEqual(room_type.total_rooms, 12)
        self.assertEqual(room_type.available_rooms, 8)
        self.assertEqual(room_type.amenities, ['Wi-Fi', 'Breakfast', 'Balcony'])
        self.assertEqual(room_type.price_per_night.amount, Decimal('240.00'))

        edit_response = self.client.post(
            rooms_url,
            {
                'action': 'save_room_type',
                'room_type_id': room_type.id,
                'room-name': 'Deluxe King',
                'room-description': 'Renovated room with a city view.',
                'room-price_amount': '265.00',
                'room-currency': 'USD',
                'room-max_occupancy': 4,
                'room-total_rooms': 10,
                'room-available_rooms': 6,
                'room-size_sqm': 45,
                'room-bed_type': 'King bed',
                'room-amenities': 'Wi-Fi\nBreakfast',
                'room-is_active': 'on',
            },
        )
        room_type.refresh_from_db()

        self.assertRedirects(edit_response, rooms_url)
        self.assertEqual(room_type.max_occupancy, 4)
        self.assertEqual(room_type.total_rooms, 10)
        self.assertEqual(room_type.available_rooms, 6)
        self.assertEqual(room_type.price_per_night.amount, Decimal('265.00'))

        page_response = self.client.get(rooms_url)
        self.assertContains(page_response, 'Deluxe King')
        self.assertContains(page_response, '6 / 10 rooms')

        self.client.logout()
        public_response = self.client.get(
            reverse('hotels:hotel_detail', args=[self.hotel.id])
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, 'Deluxe King')
        self.assertContains(public_response, '6 rooms left')

    def test_room_category_rejects_more_available_than_total(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        response = self.client.post(
            reverse(
                'partners_dashboard:manage_hotel_rooms',
                args=[self.hotel.id],
            ),
            {
                'action': 'save_room_type',
                'room-name': 'Impossible Room',
                'room-description': 'Invalid capacity test.',
                'room-price_amount': '100.00',
                'room-currency': 'USD',
                'room-max_occupancy': 2,
                'room-total_rooms': 2,
                'room-available_rooms': 3,
                'room-size_sqm': '',
                'room-bed_type': '',
                'room-amenities': '',
                'room-is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Available rooms cannot exceed the total number of rooms.',
        )
        self.assertFalse(RoomType.objects.filter(name='Impossible Room').exists())

    def test_partner_can_publish_date_based_room_availability(self):
        room_type = RoomType.objects.create(
            hotel=self.hotel,
            name='Executive Suite',
            description='Suite inventory',
            max_occupancy=4,
            total_rooms=5,
            available_rooms=4,
            price_per_night='300.00',
        )
        start_date = timezone.localdate() + timezone.timedelta(days=5)
        end_date = start_date + timezone.timedelta(days=2)
        self.client.login(email='partner@example.com', password='StrongPass123!')

        response = self.client.post(
            reverse(
                'partners_dashboard:manage_hotel_rooms',
                args=[self.hotel.id],
            ),
            {
                'action': 'set_room_availability',
                'availability-room_type': room_type.id,
                'availability-start_date': start_date.isoformat(),
                'availability-end_date': end_date.isoformat(),
                'availability-available_rooms': 3,
                'availability-price_amount': '325.00',
                'availability-currency': 'USD',
            },
        )

        self.assertEqual(response.status_code, 302)
        records = HotelAvailability.objects.filter(
            room_type=room_type,
            date__range=(start_date, end_date),
        ).order_by('date')
        self.assertEqual(records.count(), 3)
        self.assertTrue(all(record.available_rooms == 3 for record in records))
        self.assertTrue(
            all(record.price_per_night.amount == Decimal('325.00') for record in records)
        )

        self.client.logout()
        availability_response = self.client.get(
            reverse('hotels:check_availability', args=[self.hotel.id]),
            {
                'check_in': start_date.isoformat(),
                'check_out': (end_date + timezone.timedelta(days=1)).isoformat(),
            },
        )
        availability_payload = availability_response.json()
        self.assertTrue(availability_payload['available'])
        self.assertEqual(
            Decimal(str(availability_payload['total_price'])),
            Decimal('975.00'),
        )

    def test_partner_cannot_manage_another_partners_rooms(self):
        other_user = User.objects.create_user(
            email='roomowner@example.com',
            username='roomowner',
            password='StrongPass123!',
            first_name='Room',
            last_name='Owner',
        )
        other_partner = Partner.objects.create(
            user=other_user,
            company_name='Room Owner Co',
        )
        other_hotel = Hotel.objects.create(
            name='Private Rooms Hotel',
            description='Another partner hotel',
            city=self.city,
            address='Nairobi',
            price_per_night='180.00',
        )
        HotelPartner.objects.create(
            owner=other_user,
            hotel=other_hotel,
            partner_name='Room Owner Co',
            partner_id='ROOM-OWNER-1',
            partner_profile=other_partner,
        )
        self.client.login(email='partner@example.com', password='StrongPass123!')

        response = self.client.get(
            reverse(
                'partners_dashboard:manage_hotel_rooms',
                args=[other_hotel.id],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_partner_can_view_and_filter_owned_reservations(self):
        pending_booking = self.create_booking()
        confirmed_booking = self.create_booking(
            service=self.car,
            status='confirmed',
            email='confirmed@example.com',
        )
        self.client.login(email='partner@example.com', password='StrongPass123!')

        list_response = self.client.get(
            reverse('partners_dashboard:manage_reservations'),
            {'status': 'pending', 'service': 'hotel', 'q': pending_booking.booking_reference},
        )
        detail_response = self.client.get(
            reverse(
                'partners_dashboard:reservation_detail',
                args=[pending_booking.id],
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, pending_booking.booking_reference)
        self.assertNotContains(list_response, confirmed_booking.booking_reference)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, 'Grace Guest')
        self.assertContains(detail_response, 'Late arrival requested.')

    def test_partner_can_confirm_and_complete_reservation(self):
        booking = self.create_booking()
        self.client.login(email='partner@example.com', password='StrongPass123!')

        confirm_response = self.client.post(
            reverse(
                'partners_dashboard:update_reservation_status',
                args=[booking.id],
            ),
            {'action': 'confirm'},
        )
        booking.refresh_from_db()

        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(booking.status, 'confirmed')

        complete_response = self.client.post(
            reverse(
                'partners_dashboard:update_reservation_status',
                args=[booking.id],
            ),
            {'action': 'complete'},
        )
        booking.refresh_from_db()

        self.assertEqual(complete_response.status_code, 302)
        self.assertEqual(booking.status, 'completed')

        invalid_response = self.client.post(
            reverse(
                'partners_dashboard:update_reservation_status',
                args=[booking.id],
            ),
            {'action': 'confirm'},
            follow=True,
        )
        booking.refresh_from_db()

        self.assertEqual(booking.status, 'completed')
        self.assertContains(
            invalid_response,
            'Completed reservations cannot be confirmed.',
        )

    def test_partner_can_manage_availability_for_all_service_types(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        services = [
            ('hotel', self.hotel),
            ('flight', self.flight),
            ('car', self.car),
            ('tour', self.tour),
        ]

        for service_type, service in services:
            response = self.client.post(
                reverse(
                    'partners_dashboard:set_property_availability',
                    args=[service_type, service.id],
                ),
                {'available': 'false'},
            )
            self.assertRedirects(
                response,
                reverse('partners_dashboard:manage_properties'),
            )

        self.hotel.refresh_from_db()
        self.flight.refresh_from_db()
        self.car.refresh_from_db()
        self.tour.refresh_from_db()
        self.assertFalse(self.hotel.is_available)
        self.assertEqual(self.flight.status, 'cancelled')
        self.assertFalse(self.car.is_available)
        self.assertFalse(self.tour.is_available)

        for service_type, service in [
            ('hotel', self.hotel),
            ('flight', self.flight),
            ('car', self.car),
            ('tour', self.tour),
        ]:
            self.client.post(
                reverse(
                    'partners_dashboard:set_property_availability',
                    args=[service_type, service.id],
                ),
                {'available': 'true'},
            )

        self.hotel.refresh_from_db()
        self.flight.refresh_from_db()
        self.car.refresh_from_db()
        self.tour.refresh_from_db()
        self.assertTrue(self.hotel.is_available)
        self.assertEqual(self.flight.status, 'scheduled')
        self.assertTrue(self.car.is_available)
        self.assertTrue(self.tour.is_available)

    def test_flight_without_seats_cannot_be_reopened(self):
        self.flight.status = 'cancelled'
        self.flight.available_seats = 0
        self.flight.save(update_fields=['status', 'available_seats'])
        self.client.login(email='partner@example.com', password='StrongPass123!')

        response = self.client.post(
            reverse(
                'partners_dashboard:set_property_availability',
                args=['flight', self.flight.id],
            ),
            {'available': 'true'},
            follow=True,
        )
        self.flight.refresh_from_db()

        self.assertEqual(self.flight.status, 'cancelled')
        self.assertContains(response, 'Add available seats before reopening this flight.')

    def test_partner_cannot_manage_another_partners_inventory_or_booking(self):
        other_user = User.objects.create_user(
            email='otherpartner@example.com',
            username='otherpartner',
            password='StrongPass123!',
            first_name='Other',
            last_name='Partner',
        )
        other_partner = Partner.objects.create(
            user=other_user,
            company_name='Other Partner',
        )
        other_hotel = Hotel.objects.create(
            name='Other Hotel',
            description='Not owned by the signed-in partner',
            city=self.city,
            address='Nairobi',
            price_per_night='99.00',
        )
        HotelPartner.objects.create(
            owner=other_user,
            hotel=other_hotel,
            partner_name='Other Partner',
            partner_id='OTHER-1',
            partner_profile=other_partner,
        )
        other_booking = self.create_booking(
            service=other_hotel,
            email='otherguest@example.com',
        )
        self.client.login(email='partner@example.com', password='StrongPass123!')

        detail_response = self.client.get(
            reverse(
                'partners_dashboard:reservation_detail',
                args=[other_booking.id],
            )
        )
        status_response = self.client.post(
            reverse(
                'partners_dashboard:update_reservation_status',
                args=[other_booking.id],
            ),
            {'action': 'confirm'},
        )
        availability_response = self.client.post(
            reverse(
                'partners_dashboard:set_property_availability',
                args=['hotel', other_hotel.id],
            ),
            {'available': 'false'},
        )

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(status_response.status_code, 404)
        self.assertEqual(availability_response.status_code, 404)
        other_booking.refresh_from_db()
        other_hotel.refresh_from_db()
        self.assertEqual(other_booking.status, 'pending')
        self.assertTrue(other_hotel.is_available)

    def test_reservation_export_contains_only_partner_records(self):
        own_booking = self.create_booking()
        other_user = User.objects.create_user(
            email='exportpartner@example.com',
            username='exportpartner',
            password='StrongPass123!',
            first_name='Export',
            last_name='Partner',
        )
        other_partner = Partner.objects.create(user=other_user, company_name='Export Co')
        other_tour = Tour.objects.create(
            operator=self.operator,
            category=self.category,
            name='Other Tour',
            description='Other partner tour',
            destination=self.city,
            meeting_point='Nairobi',
            meeting_address='Nairobi',
            price_per_person='80.00',
            start_time='09:00:00',
            end_time='12:00:00',
            partner_profile=other_partner,
        )
        other_booking = self.create_booking(
            service=other_tour,
            email='exportguest@example.com',
        )
        self.client.login(email='partner@example.com', password='StrongPass123!')

        response = self.client.get(reverse('partners_dashboard:export_reservations'))
        csv_content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn(own_booking.booking_reference, csv_content)
        self.assertNotIn(other_booking.booking_reference, csv_content)

    def test_offline_inventory_is_hidden_and_cannot_be_booked(self):
        self.client.login(email='partner@example.com', password='StrongPass123!')
        self.client.post(
            reverse(
                'partners_dashboard:set_property_availability',
                args=['hotel', self.hotel.id],
            ),
            {'available': 'false'},
        )
        self.client.post(
            reverse(
                'partners_dashboard:set_property_availability',
                args=['flight', self.flight.id],
            ),
            {'available': 'false'},
        )
        self.client.logout()

        hotel_list_response = self.client.get(reverse('hotels:hotel_list'))
        hotel_detail_response = self.client.get(
            reverse('hotels:hotel_detail', args=[self.hotel.id])
        )
        flight_list_response = self.client.get(reverse('flights:flight_list'))
        search_response = self.client.get(
            reverse('search'),
            {'q': 'Skyline', 'type': 'all'},
        )
        api_detail_response = self.client.get(f'/api/v1/hotels/{self.hotel.id}/')

        self.assertNotContains(hotel_list_response, self.hotel.name)
        self.assertEqual(hotel_detail_response.status_code, 404)
        self.assertNotContains(flight_list_response, self.flight.flight_number)
        self.assertNotIn(self.hotel, search_response.context['results']['hotels'])
        self.assertEqual(api_detail_response.status_code, 404)

        customer = User.objects.create_user(
            email='offlineguest@example.com',
            username='offlineguest',
            password='StrongPass123!',
            first_name='Offline',
            last_name='Guest',
        )
        self.client.login(email=customer.email, password='StrongPass123!')
        booking_response = self.client.post(
            reverse('bookings:create_booking'),
            {
                'service_type': 'hotel',
                'service_id': self.hotel.id,
                'booking_date': (
                    timezone.now().date() + timezone.timedelta(days=7)
                ).isoformat(),
                'check_in': (
                    timezone.now().date() + timezone.timedelta(days=7)
                ).isoformat(),
                'check_out': (
                    timezone.now().date() + timezone.timedelta(days=9)
                ).isoformat(),
                'guests': 2,
                'contact_name': 'Offline Guest',
                'contact_email': customer.email,
            },
        )

        self.assertEqual(booking_response.status_code, 404)
        self.assertFalse(Booking.objects.filter(user=customer).exists())

    def test_customer_cannot_self_confirm_booking_through_api(self):
        customer = User.objects.create_user(
            email='apiguest@example.com',
            username='apiguest',
            password='StrongPass123!',
            first_name='API',
            last_name='Guest',
        )
        self.client.login(email=customer.email, password='StrongPass123!')

        response = self.client.post(
            '/api/v1/bookings/',
            {
                'content_type': ContentType.objects.get_for_model(self.hotel).id,
                'object_id': self.hotel.id,
                'booking_date': (
                    timezone.now().date() + timezone.timedelta(days=7)
                ).isoformat(),
                'total_amount': '450.00',
                'status': 'confirmed',
                'contact_name': 'API Guest',
                'contact_email': customer.email,
                'contact_phone': '+2348000000001',
                'special_requests': '',
            },
        )

        self.assertEqual(response.status_code, 201, response.content)
        booking = Booking.objects.get(user=customer)
        self.assertEqual(booking.status, 'pending')


class PartnerAccessAndLocationTests(TestCase):
    def setUp(self):
        self.partner_user = User.objects.create_user(
            email='locations@example.com',
            username='locationpartner',
            password='StrongPass123!',
            first_name='Lara',
            last_name='Locations',
        )
        self.partner = Partner.objects.create(
            user=self.partner_user,
            company_name='Global Location Partners',
        )
        self.regular_user = User.objects.create_user(
            email='traveller@example.com',
            username='traveller',
            password='StrongPass123!',
            first_name='Terry',
            last_name='Traveller',
        )

    def test_anonymous_user_is_sent_to_sign_in(self):
        response = self.client.get(reverse('partners_dashboard:partners_dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={reverse('partners_dashboard:partners_dashboard')}",
            fetch_redirect_response=False,
        )

    def test_partner_sign_in_redirects_to_partner_dashboard(self):
        response = self.client.post(
            reverse('account_login'),
            {
                'login': self.partner_user.email,
                'password': 'StrongPass123!',
            },
        )

        self.assertRedirects(
            response,
            reverse('partners_dashboard:partners_dashboard'),
            fetch_redirect_response=False,
        )

    def test_regular_user_cannot_access_partner_tools(self):
        self.client.login(email=self.regular_user.email, password='StrongPass123!')

        locations_response = self.client.get(
            reverse('partners_dashboard:manage_locations')
        )
        property_response = self.client.get(
            reverse('partners_dashboard:create_hotel_property')
        )

        self.assertEqual(locations_response.status_code, 403)
        self.assertEqual(property_response.status_code, 403)
        self.assertFalse(Partner.objects.filter(user=self.regular_user).exists())

    def test_inactive_partner_cannot_access_dashboard(self):
        self.partner.is_active = False
        self.partner.save(update_fields=['is_active'])
        self.client.login(email=self.partner_user.email, password='StrongPass123!')

        response = self.client.get(reverse('partners_dashboard:partners_dashboard'))

        self.assertEqual(response.status_code, 403)

    def test_partner_can_add_country_and_city(self):
        self.client.login(email=self.partner_user.email, password='StrongPass123!')

        country_response = self.client.post(
            reverse('partners_dashboard:manage_locations'),
            {
                'action': 'add_country',
                'country-name': 'Nigeria',
                'country-code': 'NG',
                'country-currency': '',
                'country-timezone': 'Africa/Lagos',
                'country-is_active': 'on',
            },
        )

        self.assertRedirects(
            country_response,
            reverse('partners_dashboard:manage_locations'),
        )
        country = Country.objects.get(name='Nigeria')
        self.assertEqual(str(country.code), 'NG')

        city_response = self.client.post(
            reverse('partners_dashboard:manage_locations'),
            {
                'action': 'add_city',
                'city-name': 'Abuja',
                'city-country': country.id,
                'city-latitude': '9.07650000',
                'city-longitude': '7.39860000',
                'city-is_popular': 'on',
                'city-is_active': 'on',
            },
        )

        self.assertRedirects(
            city_response,
            reverse('partners_dashboard:manage_locations'),
        )
        city = City.objects.get(name='Abuja', country=country)
        self.assertTrue(city.is_popular)
        self.assertTrue(city.is_active)

    def test_duplicate_location_is_rejected_with_visible_error(self):
        Country.objects.create(name='Nigeria', code='NG', timezone='Africa/Lagos')
        self.client.login(email=self.partner_user.email, password='StrongPass123!')

        response = self.client.post(
            reverse('partners_dashboard:manage_locations'),
            {
                'action': 'add_country',
                'country-name': 'nigeria',
                'country-code': 'NG',
                'country-currency': '',
                'country-timezone': 'Africa/Lagos',
                'country-is_active': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This country already exists.')
        self.assertContains(response, 'This country code already exists.')
        self.assertEqual(Country.objects.filter(name__iexact='Nigeria').count(), 1)
