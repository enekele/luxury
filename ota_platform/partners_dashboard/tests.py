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
