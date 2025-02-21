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
            "defaults": {
                "concurrency": 1, 
                "timeout": 30000
            },
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
            "/admin/analytics/export_data_type/",
            "/admin/analytics/export_data_domain_requests_full/",
            "/admin/analytics/export_data_full/",
            "/admin/analytics/export_data_federal/",
            "/admin/analytics/export_domains_growth/",
            "/admin/analytics/export_requests_growth/",
            "/admin/analytics/export_managed_domains/",
            "/admin/analytics/export_unmanaged_domains/",
        }

        path = urlparse(url).path
        if path in exclude_endpoints:
            return True

        path_segments = [seg for seg in path.split("/") if seg]
        return any(segment in exclude_segments for segment in path_segments)

    @staticmethod
    def substitute_regex_params(route: str) -> str:
        """
        Replace regex named capture groups with dummy values.
        Args:
            route (str): The regex string.
        Returns:
            str: The regex string with named groups replaced by dummy values.
        """
        regex = r"\(\?P<(\w+)>([^)]+)\)"
        if route == "(?P<app_label>auditlog|registrar)/":
            return re.sub(regex, "registrar", route)
        else:
            return re.sub(regex, "1", route)

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

    @staticmethod
    def substitute_params(route: str, full_path: str = "") -> str:
        """
        Replace URL parameters with dummy values.
        Args:
            route (str): The route string (e.g. "domain/<int:pk>/delete")
            full_path (str): The complete path including prefixes
        Returns:
            str: The route with parameters replaced.
        """
        # Check both the route and the full path for admin
        hardcoded_id = "1" if ("admin/" in route or "admin/" in full_path) else "9999"
        return re.sub(r"<[^>]+>", hardcoded_id, route)

    def extract_urls(self, urlpatterns, prefix: str = "") -> list:
        """
        Recursively extract URLs from the provided urlpatterns list.
        """
        urls = []
        for pattern in urlpatterns:
            if hasattr(pattern.pattern, "_route"):
                route = self.substitute_params(pattern.pattern._route, prefix)
            else:
                # For regex patterns, remove anchors and substitute named groups
                route = pattern.pattern.regex.pattern
                if route.startswith("^"):
                    route = route[1:]
                if route.endswith("$"):
                    route = route[:-1]
                route = self.substitute_regex_params(route)
            
            full_route = prefix + route
            if not full_route.endswith("/"):
                full_route += "/"

            full_url = f"{BASE_URL}{full_route}"
            if isinstance(pattern, URLPattern) and not self.should_exclude(full_url):
                urls.append(full_url)
            elif isinstance(pattern, URLResolver):
                urls.extend(self.extract_urls(pattern.url_patterns, prefix=full_route))
        return urls
