from django.test import TestCase


class PublicPageSmokeTests(TestCase):
    def test_public_pages_render(self):
        urls = [
            '/',
            '/hotels/',
            '/flights/',
            '/cars/',
            '/tours/',
            '/events/',
            '/accounts/login/',
            '/api/v1/',
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

    def test_health_check(self):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
