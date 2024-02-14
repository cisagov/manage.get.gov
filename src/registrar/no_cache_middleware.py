"""Middleware to add Cache-control: no-cache to every response.

Used to force Cloudfront caching to leave us alone while we develop
better caching responses.
"""


class NoCacheMiddleware:
    """Middleware to add a single header to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "no-cache"
        return response
