from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Country, City
from flights.models import Airline, Airport, Flight
from hotels.models import Hotel, HotelPartner
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
