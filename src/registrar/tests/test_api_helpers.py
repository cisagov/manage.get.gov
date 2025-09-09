from unittest.mock import patch, Mock
from django.test import SimpleTestCase
from requests.exceptions import ConnectionError, Timeout, HTTPError
from registrar.utility.api_helpers import make_api_request


class TestMakeAPIRequest(SimpleTestCase):
    """Test cases for the make_api_request function"""

    @patch("registrar.utility.api_helpers.requests.request")
    def test_successful_json_response(self, mock_request):
        """Test successful API request with JSON response"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "name": "Jalaya Doe"}
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = make_api_request("https://api.example.com/users/1")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"id": 1, "name": "Jalaya Doe"})
        self.assertEqual(result["status_code"], 200)

        # Verify request was called correctly
        mock_request.assert_called_once_with(
            method="GET", url="https://api.example.com/users/1", json=None, headers=None, timeout=30, verify=True
        )

    @patch("registrar.utility.api_helpers.requests.request")
    def test_successful_text_response(self, mock_request):
        """Test successful API request with non-JSON response"""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.text = "Plain text response"
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = make_api_request("https://api.example.com/health")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], "Plain text response")
        self.assertEqual(result["status_code"], 200)

    @patch("registrar.utility.api_helpers.requests.request")
    def test_post_request_with_data(self, mock_request):
        """Test POST request with JSON data"""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 2, "created": True}
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        test_data = {"name": "Justice Doe", "email": "Justice@example.com"}
        result = make_api_request(
            "https://api.example.com/users", method="POST", headers={"Content-Type": "application/json"}, data=test_data
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"id": 2, "created": True})

        # Verify POST data was passed correctly
        mock_request.assert_called_once_with(
            method="POST",
            url="https://api.example.com/users",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30,
            verify=True,
        )

    @patch("registrar.utility.api_helpers.requests.request")
    def test_connection_error(self, mock_request):
        """Test handling of connection errors"""
        mock_request.side_effect = ConnectionError("Connection failed")

        result = make_api_request("https://api.example.com/users/1")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "connection_error")
        self.assertEqual(result["message"], "Unable to connect to the server")
        self.assertIn("Connection failed", result["details"])

    @patch("registrar.utility.api_helpers.requests.request")
    def test_timeout_error(self, mock_request):
        """Test handling of timeout errors"""
        mock_request.side_effect = Timeout("Request timed out")

        result = make_api_request("https://api.example.com/users/1", timeout=10)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "timeout")
        self.assertEqual(result["message"], "Request timed out after 10 seconds")
        self.assertIn("Request timed out", result["details"])

    @patch("registrar.utility.api_helpers.requests.request")
    def test_http_error_404(self, mock_request):
        """Test handling of HTTP 404 error"""
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = HTTPError("404 Client Error")
        http_error.response = mock_response
        mock_request.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        result = make_api_request("https://api.example.com/users/999")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "http_error")
        self.assertEqual(result["status_code"], 404)
        self.assertEqual(result["message"], "Not found - resource does not exist")

    @patch("registrar.utility.api_helpers.requests.request")
    def test_http_error_500(self, mock_request):
        """Test handling of HTTP 500 error"""
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = HTTPError("500 Server Error")
        http_error.response = mock_response
        mock_request.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error

        result = make_api_request("https://api.example.com/users/1")

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "http_error")
        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["message"], "Internal server error")

    @patch("registrar.utility.api_helpers.requests.request")
    def test_custom_headers(self, mock_request):
        """Test request with custom headers"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        custom_headers = {"Authorization": "Bearer token123", "Content-Type": "application/json"}
        result = make_api_request("https://api.example.com/users/1", headers=custom_headers)

        self.assertTrue(result["success"])

        # Verify headers were merged correctly
        expected_headers = {"Content-Type": "application/json", "Authorization": "Bearer token123"}
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[1]["headers"], expected_headers)
