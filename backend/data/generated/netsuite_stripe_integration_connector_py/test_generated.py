import unittest
from netsuite_stripe_integration_connector import NetsuiteStripeIntegrationConnector

class TestNetsuiteStripeIntegrationConnector(unittest.TestCase):
    def setUp(self):
        self.connector = NetsuiteStripeIntegrationConnector('client_id', 'client_secret', 'https://rest.netsuite.com')

    def test_authenticate(self):
        self.assertTrue(self.connector.authenticate())

    def test_create_record(self):
        record = self.connector.create_record('customers', {'name': 'John Doe', 'email': 'john.doe@example.com'})
        self.assertIsNotNone(record)

    def test_get_record(self):
        record = self.connector.get_record('customers', '123')
        self.assertIsNotNone(record)

    def test_update_record(self):
        record = self.connector.update_record('customers', '123', {'name': 'Jane Doe', 'email': 'jane.doe@example.com'})
        self.assertIsNotNone(record)

    def test_delete_record(self):
        self.assertTrue(self.connector.delete_record('customers', '123'))

    def test_list_records(self):
        records = self.connector.list_records('customers')
        self.assertIsNotNone(records)

if __name__ == '__main__':
    unittest.main()