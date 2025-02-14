import os
import re
import json
from urllib.parse import urlparse
from django.urls import URLPattern, URLResolver, get_resolver
from django.core.management.base import BaseCommand

BASE_URL = "http://localhost:8080/"
class Command(BaseCommand):
    """
    Generate the .pa11yci configuration file with all URLs from Django's URLconf.
    """
    help = (
        "Generates the .pa11yci file with all URLs found in the URLconf, "
        "with dynamic parameters substituted with dummy values and some endpoints excluded."
    )

    def handle(self, *args, **options):
        """
        Generate and write the .pa11yci configuration file to the current working directory.
        """
        resolver = get_resolver()
        urls = self.extract_urls(resolver.url_patterns)
        config = {
            "defaults": {"concurrency": 1, "timeout": 30000},
            "viewport": {
                "width": 1920,
                "height": 1080
            },
            "actions": [
                "wait for url to be #"
            ],
            "urls": urls,
        }
        output_file = os.path.join(os.getcwd(), ".pa11yci")
        with open(output_file, "w") as f:
            json.dump(config, f, indent=4)
        self.stdout.write(self.style.SUCCESS(f"Generated {output_file} with {len(urls)} URLs."))

    def should_exclude(self, url: str) -> bool:
        """
        Checks whether a given URL should be excluded based on predefined patterns.
        
        Args:
            url (str): The full URL to test.
        Returns:
            bool: True if URL should be skipped; otherwise False.
        """
        exclude_segments = [
            "__debug__",
            "api",
            "jsi18n",
            "r",
            "health",
            "todo",
            "autocomplete",
            "openid",
            "logout",
            "login",
            "password_change",
            "reports"
        ]
        
        # Specific endpoints to exclude
        exclude_endpoints = {
            "/get-domains-json/",
            "/get-domain-requests-json/",
            "/get-portfolio-members-json/",
            "/get-member-domains-json/",
            "http://localhost:8080/admin/analytics/export_data_type/",
            "http://localhost:8080/admin/analytics/export_data_domain_requests_full/",
            "http://localhost:8080/admin/analytics/export_data_full/",
            "http://localhost:8080/admin/analytics/export_data_federal/",
            "http://localhost:8080/admin/analytics/export_domains_growth/",
            "http://localhost:8080/admin/analytics/export_requests_growth/",
            "http://localhost:8080/admin/analytics/export_managed_domains/",
            "http://localhost:8080/admin/analytics/export_unmanaged_domains/",
        }

        # Parse the URL and get the path
        path = urlparse(url).path

        # Check for specific endpoints
        if path in exclude_endpoints:
            return True
        
        # Split path into segments and remove empty strings
        path_segments = [seg for seg in path.split("/") if seg]
        
        # Check if any segment matches our exclude list
        return any(segment in exclude_segments for segment in path_segments)

    @staticmethod
    def substitute_params(route: str) -> str:
        """
        Replace URL parameters with dummy values.
        Args:
            route (str): The route string (e.g. "domain/<int:pk>/delete")
        Returns:
            str: The route with parameters replaced.
        """
        return re.sub(r"<[^>]+>", "9999", route)

    @staticmethod
    def substitute_regex_params(route: str) -> str:
        """
        Replace regex named capture groups with dummy values.
        Args:
            route (str): The regex string.
        Returns:
            str: The regex string with named groups replaced by dummy values.
        """
        return re.sub(r"\(\?P<(\w+)>([^)]+)\)", "1", route)

    def get_route(self, pattern) -> str:
        """
        Extract the route string from a URLPattern or URLResolver, applying appropriate substitutions.
        
        Args:
            pattern: An instance of a Django URL pattern (either using RoutePattern or RegexPattern).
        Returns:
            str: The processed route string.
        """
        if hasattr(pattern.pattern, "_route"):
            route = pattern.pattern._route
            return self.substitute_params(route)
        else:
            # For regex patterns, remove anchors and substitute named groups.
            route = pattern.pattern.regex.pattern
            if route.startswith("^"):
                route = route[1:]
            if route.endswith("$"):
                route = route[:-1]
            return self.substitute_regex_params(route)

    def extract_urls(self, urlpatterns, prefix: str = "") -> list:
        """
        Recursively extract URLs from the provided urlpatterns list.
        
        Args:
            urlpatterns (list): A list of URLPattern and URLResolver objects.
            prefix (str): The accumulated prefix for nested patterns.
        Returns:
            list: A list of fully constructed URLs with BASE_URL prepended.
        """
        urls = []
        for pattern in urlpatterns:
            route = prefix + self.get_route(pattern)
            if not route.endswith("/"):
                route += "/"

            full_url = f"{BASE_URL}{route}"
            if isinstance(pattern, URLPattern) and not self.should_exclude(full_url):
                urls.append(full_url)
            elif isinstance(pattern, URLResolver):
                urls.extend(self.extract_urls(pattern.url_patterns, prefix=route))
        return urls
