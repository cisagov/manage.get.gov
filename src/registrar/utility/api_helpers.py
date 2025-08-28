import logging
import requests
from requests.exceptions import RequestException, ConnectionError, HTTPError, Timeout, TooManyRedirects

logger = logging.getLogger(__name__)


def make_api_request(url, method="GET", data=None, headers=None, params=None, timeout=30):
    """
    Make an HTTP request with comprehensive error handling

    Args:
        url (str): The URL to make the request to
        method (str): HTTP method (GET, POST, PUT, DELETE)
        data (dict): Request payload for POST/PUT requests
        headers (dict): Custom headers
        timeout (int): Request timeout in seconds

    Returns:
        dict: Response data or error information
    """

    try:
        # Make the request
        response = requests.request(
            method=method.upper(),
            url=url,
            json=data if data else None,
            headers=headers,
            timeout=timeout,
            verify=True,  # SSL verification
        )

        # Raise an exception for bad status codes (4xx, 5xx)
        response.raise_for_status()

        # Try to parse JSON response
        try:
            return {"success": True, "data": response.json(), "status_code": response.status_code}
        except ValueError:
            # Response is not JSON
            return {"success": True, "data": response.text, "status_code": response.status_code}

    except ConnectionError as e:
        logger.error(f"Connection error for {url}: {str(e)}")
        return {
            "success": False,
            "error": "connection_error",
            "message": "Unable to connect to the server",
            "details": str(e),
        }

    except Timeout as e:
        logger.error(f"Timeout error for {url}: {str(e)}")
        return {
            "success": False,
            "error": "timeout",
            "message": f"Request timed out after {timeout} seconds",
            "details": str(e),
        }

    except HTTPError as e:
        logger.error(f"HTTP error for {url}: {str(e)}")
        status_code = e.response.status_code if e.response else None

        # Handle different HTTP error codes
        error_messages = {
            400: "Bad request - invalid parameters",
            401: "Unauthorized - invalid credentials",
            403: "Forbidden - access denied",
            404: "Not found - resource does not exist",
            429: "Too many requests - rate limit exceeded",
            500: "Internal server error",
            502: "Bad gateway",
            503: "Service unavailable",
            504: "Gateway timeout",
        }

        return {
            "success": False,
            "error": "http_error",
            "status_code": status_code,
            "message": error_messages.get(status_code, f"HTTP error {status_code}"),
            "details": str(e),
        }

    except TooManyRedirects as e:
        logger.error(f"Too many redirects for {url}: {str(e)}")
        return {"success": False, "error": "too_many_redirects", "message": "Too many redirects", "details": str(e)}

    except RequestException as e:
        # Catch-all for other requests exceptions
        logger.error(f"Request exception for {url}: {str(e)}")
        return {
            "success": False,
            "error": "request_error",
            "message": "An error occurred while making the request",
            "details": str(e),
        }

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error for {url}: {str(e)}")
        return {
            "success": False,
            "error": "unexpected_error",
            "message": "An unexpected error occurred",
            "details": str(e),
        }
