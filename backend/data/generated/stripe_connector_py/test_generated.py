import unittest
from unittest.mock import Mock, patch

import requests

from stripe_connector import StripeConnector, ConnectorError


class StripeConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = StripeConnector(base_url="https://api.example.com", token="secret-token")

    def test_authenticate_requires_token(self) -> None:
        self.connector.token = ""
        with self.assertRaises(ConnectorError):
            self.connector.authenticate()

    @patch.object(requests.Session, "request")
    def test_create_record(self, mock_request: Mock) -> None:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"id":"1"}'
        mock_response.json.return_value = {"id": "1"}
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = self.connector.create_record("records", {"name": "demo"})
        self.assertEqual(result["id"], "1")

    @patch.object(requests.Session, "request")
    def test_retries_raise_connector_error(self, mock_request: Mock) -> None:
        mock_request.side_effect = requests.RequestException("boom")
        with self.assertRaises(ConnectorError):
            self.connector.get_record("records", "1")


if __name__ == "__main__":
    unittest.main()