import json
import sys
from django.db import connection
import subprocess
from django.test import LiveServerTestCase
from django.urls import reverse
from .common import create_superuser

class TestPa11yAccessibility(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create superuser for admin access
        cls.superuser = create_superuser()
        
        # Set up pa11y config for single page testing
        cls.pa11y_config = {
            "defaults": {
                "timeout": 30000,
                "viewport": {
                    "width": 1920,
                    "height": 1080
                },
                "actions": [
                    "wait for url to be #",
                ],
            }
        }
    
    # IDEA: This all shouldn't be relying on the dockerifle at all.
    # instead this should literally just be getting script content.
    # If we have a management file, and it prints *to a file* or we otherwise read what it would...
    # Then we can simply just read the report.
    def setUp(self):
        super().setUp()
        # Clean up any existing data with CASCADE
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS waffle_flag CASCADE')
            cursor.execute('DROP TABLE IF EXISTS waffle_flag_groups CASCADE')
            cursor.execute('DROP TABLE IF EXISTS waffle_flag_users CASCADE')

    def run_pa11y(self, url):
        """Run pa11y on a single URL and return results"""
        config_path = "registrar/tests/data/pa11y_temp.json"
        self.pa11y_config["urls"] = [f"{self.live_server_url}{url}"]
        print(f"the pa11y configs are: {self.pa11y_config}")
        with open(config_path, "w") as f:
            json.dump(self.pa11y_config, f)

        try:
            result = subprocess.run(
                ["pa11y-ci", "--config", config_path, "--json"],
                capture_output=True,
                text=True
            )
            print("\nCommand output:", file=sys.stderr)
            print("STDOUT:", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print("\nSTDERR:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return json.loads(result.stdout) if result.stdout else None
        except subprocess.CalledProcessError as e:
            return json.loads(e.output) if e.output else None

    def test_domain_requests_page_accessibility(self):
        """Test accessibility of domain requests page"""
        url = reverse("domain-requests")
        results = self.run_pa11y(url)
        
        self.assertIsNotNone(results, "Pa11y results should not be None")
        self.assertEqual(
            len(results.get("errors", [])), 
            0, 
            f"Accessibility errors found: {json.dumps(results.get('errors', []), indent=2)}"
        )

    def test_domain_list_page_accessibility(self):
        """Test accessibility of domains list page"""
        url = reverse("domains")
        results = self.run_pa11y(url)
        
        self.assertIsNotNone(results, "Pa11y results should not be None")
        self.assertEqual(
            len(results.get("errors", [])), 
            0, 
            f"Accessibility errors found: {json.dumps(results.get('errors', []), indent=2)}"
        )
