from django.test import Client, TestCase


class HealthTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_check_endpoint(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
