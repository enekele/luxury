from django.test import TestCase
from django.urls import reverse

from .models import User


class SignupTests(TestCase):
    def test_signup_creates_complete_profile_without_email_block(self):
        response = self.client.post(
            reverse('account_signup'),
            {
                'first_name': 'Olivia',
                'last_name': 'Harrison',
                'email': 'olivia@example.com',
                'password1': 'SafeExamplePass!4729',
                'password2': 'SafeExamplePass!4729',
                'phone': '+1 555 010 2000',
                'terms': 'on',
                'newsletter': 'on',
            },
        )

        self.assertRedirects(response, '/')
        user = User.objects.get(email='olivia@example.com')
        self.assertEqual(user.first_name, 'Olivia')
        self.assertEqual(user.last_name, 'Harrison')
        self.assertEqual(user.phone, '+1 555 010 2000')
        self.assertTrue(user.promotional_emails)

    def test_signup_displays_password_errors(self):
        response = self.client.post(
            reverse('account_signup'),
            {
                'first_name': 'Olivia',
                'last_name': 'Harrison',
                'email': 'invalid@example.com',
                'password1': 'short',
                'password2': 'different',
                'terms': 'on',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please correct the highlighted fields.')
        self.assertContains(response, 'Password')
        self.assertFalse(User.objects.filter(email='invalid@example.com').exists())

    def test_signup_requires_terms_acceptance(self):
        response = self.client.post(
            reverse('account_signup'),
            {
                'first_name': 'Olivia',
                'last_name': 'Harrison',
                'email': 'terms@example.com',
                'password1': 'SafeExamplePass!4729',
                'password2': 'SafeExamplePass!4729',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'You must accept the Terms of Service and Privacy Policy.',
        )
        self.assertFalse(User.objects.filter(email='terms@example.com').exists())
